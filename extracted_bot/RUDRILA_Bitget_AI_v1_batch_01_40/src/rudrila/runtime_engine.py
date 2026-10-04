from __future__ import annotations
import asyncio, json, time, uuid
from dataclasses import dataclass, field
from .engine_06_10 import SignalEngine0610
from .volatility_execution import VolatilityExecutionFamily
from .news_macro import NewsMacroEngine
from .news_feeds import LiveNewsCollector,SOURCE_CLASSES
from .consensus import consensus
from .entry_rules import EntryRules
from .regime import RegimeDetector
from .risk import RiskEngine
from .exits import ExitPlanner
from .safety_layer import EmergencySafetyLayer
from .journal import TradeJournal
from .health import HealthState
from .rest_client import BitgetREST, normalize_qty, normalize_price
from .bitget_execution import DemoOrderExecutor
from .private_ws import BitgetPrivateDemoWS
from .mtf import MultiTimeframeTrend
from .breaking_news import BreakingNewsGuard
from .signals import FamilyScore
from .position_manager import PositionManager, ManagedPosition

@dataclass
class RuntimeSymbol:
    engine: SignalEngine0610 = field(default_factory=SignalEngine0610)
    vol: VolatilityExecutionFamily = field(default_factory=VolatilityExecutionFamily)
    regime: RegimeDetector = field(default_factory=RegimeDetector)
    mtf: MultiTimeframeTrend = field(default_factory=MultiTimeframeTrend)
    last_seen_open_ts:int=0
    last_seen_5m_ts:int=0
    last_processed_5m_ts:int=0
    last_seen_15m_ts:int=0
    last_processed_15m_ts:int=0
    last_processed_closed_ts:int=0
    last_scores:dict=field(default_factory=dict)
    last_decision:dict=field(default_factory=dict)
    last_entry_ms:int=0

class DemoTradingRuntime:
    def __init__(self,settings,config):
        self.s=settings; self.c=config; self.symbols=tuple(config.get('symbols',['BTCUSDT','ETHUSDT']))
        self.rest=BitgetREST(settings); self.exec=DemoOrderExecutor(settings); self.pws=BitgetPrivateDemoWS(self.exec)
        self.state={s:RuntimeSymbol() for s in self.symbols}
        self.news_engine=NewsMacroEngine(); self.news_collector=LiveNewsCollector(); self.news_score=FamilyScore.build('news_macro',0,0); self.news_last_ms=0; self.breaking=BreakingNewsGuard()
        fp=config['decision'].get('directional_core_fast_path',{})
        self.entry=EntryRules(
            config['decision']['base_entry_score'],
            config['decision']['minimum_aligned_families'],
            fast_enabled=fp.get('enabled',True),
            fast_impulse_score=fp.get('fast_impulse_core_score',45),
            trend_continuation_score=fp.get('trend_continuation_core_score',60),
            fast_min_aligned=fp.get('minimum_core_aligned_families',4),
            max_fast_spread_pct=fp.get('max_fast_path_spread_pct',0.03),
            min_fast_depth_notional=fp.get('minimum_fast_path_depth_notional',10000),
        )
        r=config['risk']; self.risk=RiskEngine(r['risk_per_trade_pct'],r['max_daily_loss_pct'],r['max_total_drawdown_pct'],r['max_open_positions'],r['max_same_direction_correlated_positions'])
        self.exits=ExitPlanner(); e=config['execution']; self.safety=EmergencySafetyLayer(e['max_spread_pct'],e['stale_market_data_ms'])
        self.journal=TradeJournal(); self.health=HealthState(); self.instruments={}
        self.day_start_equity=None; self.equity_peak=None; self.account_equity=None
        self.execution_backend='UTA_V3_DEMO'; self.demo_margin_coin='USDT'; self.classic_positions=[]; self.classic_last_ok_ms=0; self.classic_last_account_ms=0; self.legacy_sim_error=''; self.legacy_instruments={}
        self.account_last_poll_ms=0; self.account_last_ok_ms=0; self.account_poll_interval_ms=5000
        self.account_meta_last_ms=0; self.account_meta_error=''; self.account_asset_error=''; self.classic_account_error=''
        self.account_perm_type=''; self.account_permissions=[]; self.account_mode=''; self.account_level=''; self.account_hold_mode=''
        self.uta_asset_snapshot=[]; self.classic_account_snapshot=[]
        self.target_leverage=int(config.get('runtime',{}).get('default_leverage',10))
        self.leverage_ready=False; self.leverage_error=''; self.leverage_last_ms=0; self.leverage_verified={}
        pm=config.get('position_management',{})
        self.posmgr=PositionManager(
            be_trigger_r=pm.get('breakeven_trigger_r',.8),
            trail_trigger_r=pm.get('trailing_trigger_r',1.2),
            max_hold_ms=int(float(pm.get('max_hold_minutes',45))*60_000),
            opposite_score=pm.get('opposite_consensus_score',60),
            opposite_aligned=pm.get('opposite_aligned_families',4),
            false_breakout_ms=int(float(pm.get('false_breakout_minutes',10))*60_000),
            false_breakout_adverse_r=pm.get('false_breakout_adverse_r',.25),
            profit_lock_trigger_r=pm.get('profit_lock_trigger_r',.9),
            profit_lock_floor_r=pm.get('profit_lock_floor_r',.25),
            trailing_giveback_r=pm.get('trailing_giveback_r',.45),
        )
        self.managed_positions={}
        self.position_exit_inflight={}

    async def _news_loop(self):
        while True:
            now=int(time.time()*1000)
            try:
                items=await asyncio.to_thread(self.news_collector.fetch)
                self.news_score=self.news_engine.aggregate(items,SOURCE_CLASSES,now) if items else self.news_engine.aggregate([],{},now)
                signed=self.news_engine.last.get('signed_score',0)
                stories=self.news_engine.last.get('stories') or []
                headline=stories[0].get('title','') if stories else ''
                self.breaking.ingest(signed,headline,now)
            except Exception:
                self.news_score=self.news_engine.aggregate([],{},now)
            self.news_last_ms=now
            await asyncio.sleep(30)

    @staticmethod
    def _usable_equity(data):
        """Return positive usable demo equity from UTA account payloads.

        Bitget UTA REST uses an account object with an assets array while the
        private account channel uses an account object with a coin array. Demo
        credits can also appear as USDT `bonus`. Never fabricate equity.
        """
        if not data:
            return 0.0
        account_rows=[]
        asset_rows=[]
        if isinstance(data,dict):
            account_rows=[data]
            asset_rows=list(data.get('assets') or data.get('coin') or [])
        elif isinstance(data,list):
            account_rows=[x for x in data if isinstance(x,dict)]
            # REST may also return a flat asset list on older shapes.
            for x in account_rows:
                nested=x.get('assets') or x.get('coin')
                if isinstance(nested,list): asset_rows.extend(nested)
            if not asset_rows and account_rows:
                asset_rows=account_rows
        def f(x):
            try: return float(x or 0)
            except Exception: return 0.0
        total=max([f(x.get('totalEquity')) for x in account_rows] or [0.0])
        usd=sum(max(0.0,f(x.get('usdValue'))) for x in asset_rows if isinstance(x,dict))
        usdt_usable=0.0
        for x in asset_rows:
            if not isinstance(x,dict):
                continue
            coin=str(x.get('coin','')).upper()
            # Bitget Demo UI/account payloads may expose the synthetic demo
            # settlement asset as SUSDT rather than USDT. SUSDT is the demo
            # USDT unit, so it is safe to treat it 1:1 for DEMO risk sizing.
            if coin not in ('USDT','SUSDT'):
                continue
            base=max(f(x.get('available')),f(x.get('equity')),f(x.get('balance')),0.0)
            bonus=max(0.0,f(x.get('bonus')))
            usdt_usable=max(usdt_usable,base+bonus)
        return max(0.0,total,usd,usdt_usable)

    @staticmethod
    def _usable_classic_equity(data):
        """Return (equity, margin_coin) from Classic Futures demo account rows."""
        rows=data if isinstance(data,list) else ([data] if isinstance(data,dict) else [])
        def f(x):
            try: return float(x or 0)
            except Exception: return 0.0
        best=(0.0,'')
        for x in rows:
            if not isinstance(x,dict): continue
            coin=str(x.get('marginCoin') or x.get('coin') or '').upper()
            if coin not in ('SUSDT','USDT'): continue
            eq=max(
                f(x.get('available')),f(x.get('accountEquity')),f(x.get('equity')),
                f(x.get('usdtEquity')),f(x.get('crossedMaxAvailable')),
                f(x.get('maxOpenPosAvailable')),f(x.get('maxTransferOut')),0.0
            )
            if eq>best[0]: best=(eq,coin)
        return best

    @staticmethod
    def _demo_display_symbol(symbol:str)->str:
        if symbol.endswith('USDT'):
            base=symbol[:-4]
            return f'S{base}SUSDT'
        return symbol

    @staticmethod
    def _legacy_sim_symbol(symbol:str)->str:
        m={'BTCUSDT':'SBTCSUSDT_SUMCBL','ETHUSDT':'SETHSUSDT_SUMCBL'}
        out=m.get(str(symbol).upper())
        if not out: raise RuntimeError('legacy simulated backend only supports BTCUSDT/ETHUSDT')
        return out

    @staticmethod
    def _same_market(a:str,b:str)->bool:
        a=str(a or '').upper(); b=str(b or '').upper()
        if a==b: return True
        def norm(x):
            if x.endswith('_SUMCBL'): x=x[:-7]
            if x.startswith('S') and x.endswith('SUSDT') and len(x)>6:
                return x[1:-5]+'USDT'
            return x
        return norm(a)==norm(b)

    def _sync_classic_positions(self, force=False):
        if self.execution_backend!='CLASSIC_V2_DEMO': return
        now=int(time.time()*1000)
        if not force and now-self.classic_last_ok_ms<2000: return
        try:
            data=self.rest.classic_positions(margin_coin=self.demo_margin_coin).get('data') or []
            self.classic_positions=[x for x in data if isinstance(x,dict)]
            self.classic_last_ok_ms=now
        except Exception as exc:
            self.classic_account_error=str(exc)[:240]
            # Keep the last known position state, but mark sync stale.
            pass

    @staticmethod
    def _sanitized_uta_assets(data):
        rows=[]
        if isinstance(data,dict):
            nested=data.get('assets') or data.get('coin')
            if isinstance(nested,list): rows=nested
            elif data.get('coin'): rows=[data]
        elif isinstance(data,list):
            rows=data
        out=[]
        for x in rows[:20]:
            if not isinstance(x,dict): continue
            out.append({k:x.get(k) for k in ('coin','available','balance','equity','usdValue','bonus') if k in x})
        return out

    @staticmethod
    def _sanitized_classic_accounts(data):
        rows=data if isinstance(data,list) else ([data] if isinstance(data,dict) else [])
        out=[]
        for x in rows[:20]:
            if not isinstance(x,dict): continue
            out.append({k:x.get(k) for k in ('marginCoin','available','accountEquity','equity','usdtEquity','crossedMaxAvailable') if k in x})
        return out

    def _refresh_account_meta(self, force=False):
        now=int(time.time()*1000)
        if not force and now-self.account_meta_last_ms<60_000: return
        self.account_meta_last_ms=now
        try:
            info=self.rest.account_info().get('data') or {}
            self.account_perm_type=str(info.get('permType') or '')
            self.account_permissions=sorted(str(x) for x in (info.get('permissions') or []))
            settings=self.rest.account_settings().get('data') or {}
            self.account_mode=str(settings.get('accountMode') or '')
            self.account_level=str(settings.get('accountLevel') or '')
            self.account_hold_mode=str(settings.get('holdMode') or '')
            self.account_meta_error=''
        except Exception as exc:
            self.account_meta_error=str(exc)[:240]

    def _equity_from_private(self, force=False):
        """Read only supported Bitget Demo balances.

        Preferred source is the UTA private WebSocket snapshot. REST is polled at
        most once every five seconds as a recovery/refresh path. Classic v2
        paptrading remains a supported fallback because Bitget documents demo
        trading for both UTA and Classic. Deprecated synthetic SUMCBL endpoints
        are deliberately not used.
        """
        now_ms=int(time.time()*1000)
        private_equity=self._usable_equity(self.exec.state.account)
        if private_equity>0:
            self.execution_backend='UTA_V3_DEMO'; self.demo_margin_coin='USDT'
            self.account_equity=private_equity; self.account_last_ok_ms=now_ms
            return private_equity

        if not force and now_ms-self.account_last_poll_ms<self.account_poll_interval_ms:
            if (self.account_equity or 0)>0 and now_ms-self.account_last_ok_ms<15_000:
                return self.account_equity
            return 0.0

        self.account_last_poll_ms=now_ms
        self._refresh_account_meta()
        try:
            raw=self.rest.account_assets().get('data')
            self.uta_asset_snapshot=self._sanitized_uta_assets(raw)
            rest_equity=self._usable_equity(raw)
            self.account_asset_error=''
            if rest_equity>0:
                self.execution_backend='UTA_V3_DEMO'; self.demo_margin_coin='USDT'
                self.account_equity=rest_equity; self.account_last_ok_ms=now_ms
                return rest_equity
        except Exception as exc:
            self.account_asset_error=str(exc)[:240]

        try:
            raw=self.rest.classic_accounts().get('data')
            self.classic_account_snapshot=self._sanitized_classic_accounts(raw)
            classic_equity,coin=self._usable_classic_equity(raw)
            self.classic_account_error=''
            if classic_equity>0:
                self.execution_backend='CLASSIC_V2_DEMO'; self.demo_margin_coin=coin or 'USDT'
                self.account_equity=classic_equity; self.account_last_ok_ms=now_ms
                self.classic_last_ok_ms=now_ms; self.classic_last_account_ms=now_ms
                self._sync_classic_positions(force=True)
                return classic_equity
        except Exception as exc:
            self.classic_account_error=str(exc)[:240]

        # Do not fabricate or borrow the balance shown in a different app/demo
        # environment. An exchange-verified positive balance is mandatory.
        self.execution_backend='UTA_V3_DEMO'; self.demo_margin_coin='USDT'
        self.account_equity=0.0
        return 0.0

    def _configure_demo_leverage(self, force=False):
        now=int(time.time()*1000)
        if not force and now-self.leverage_last_ms<60_000:
            return self.leverage_ready
        self.leverage_last_ms=now
        verified={}
        errors=[]
        for sym in self.symbols:
            try:
                if self.execution_backend=='CLASSIC_V2_DEMO':
                    ack=None; api_symbol=None; last_exc=None
                    for candidate in (sym,self._demo_display_symbol(sym)):
                        try:
                            ack=self.rest.classic_set_leverage(candidate,self.target_leverage,self.demo_margin_coin)
                            api_symbol=candidate
                            break
                        except Exception as exc:
                            last_exc=exc
                    if ack is None:
                        raise last_exc or RuntimeError('classic leverage configuration failed')
                    row=self.rest.classic_single_account(api_symbol,self.demo_margin_coin).get('data') or {}
                    lev=row.get('crossMarginLeverage') or row.get('leverage') or row.get('longLeverage')
                    if lev not in (None,'') and abs(float(lev)-self.target_leverage)>1e-9:
                        raise RuntimeError(f'leverage verification mismatch: expected {self.target_leverage} got {lev}')
                    verified[sym]={'api_symbol':api_symbol,'leverage':float(lev) if lev not in (None,'') else self.target_leverage}
                else:
                    ack=self.rest.set_leverage(sym,self.target_leverage,'crossed')
                    if str(ack.get('code')) not in ('00000','0'):
                        raise RuntimeError(f'UTA leverage set failed: {ack}')
                    verified[sym]={'api_symbol':sym,'leverage':self.target_leverage}
            except Exception as exc:
                errors.append(f'{sym}:{str(exc)[:160]}')
        self.leverage_verified=verified
        self.leverage_ready=(len(verified)==len(self.symbols) and not errors)
        self.leverage_error='; '.join(errors)[:320]
        if self.leverage_ready:
            print(f"LEVERAGE_READY target={self.target_leverage}x symbols={','.join(self.symbols)} backend={self.execution_backend}",flush=True)
        else:
            print(f"LEVERAGE_BLOCK target={self.target_leverage}x reason={self.leverage_error}",flush=True)
        return self.leverage_ready

    def _private_message(self,msg):
        if (msg.get('arg') or {}).get('topic')=='account':
            x=self._usable_equity(msg.get('data') or [])
            if x>0:
                self.account_equity=x; self.account_last_ok_ms=int(time.time()*1000)


    @staticmethod
    def _num(row:dict|None,*keys,default=0.0):
        row=row or {}
        for k in keys:
            try:
                v=row.get(k)
                if v not in (None,''):
                    return float(v)
            except Exception:
                pass
        return float(default)

    @staticmethod
    def _ts_ms(row:dict|None,*keys,default=0):
        row=row or {}
        for k in keys:
            try:
                v=int(float(row.get(k) or 0))
                if v>0:
                    return v*1000 if v<10_000_000_000 else v
            except Exception:
                pass
        return int(default or 0)

    def _classic_position_any(self,sym:str):
        for row in self.classic_positions:
            if isinstance(row,dict) and self._same_market(row.get('symbol'),sym):
                return row
        return None

    def _classic_position_active(self,sym:str):
        for row in self.classic_positions:
            if not isinstance(row,dict) or not self._same_market(row.get('symbol'),sym):
                continue
            if self._num(row,'total','available','size')>0:
                return row
        return None

    def _adopt_managed_position(self,sym:str,row:dict,mark:float,now_ms:int):
        qty=self._num(row,'total','available','size')
        if qty<=0:
            return None
        hold=str(row.get('holdSide') or row.get('posSide') or '').lower()
        side='LONG' if hold=='long' else 'SHORT' if hold=='short' else ''
        if not side:
            return None
        p=self.managed_positions.get(sym)
        entry=self._num(row,'openPriceAvg','averageOpenPrice','openPrice','avgEntryPrice','entryPrice',default=mark)
        if entry<=0: entry=mark
        if p is not None:
            p.qty=qty
            if entry>0: p.entry=entry
            return p

        opened=self._ts_ms(row,'cTime','openTime','createdTime','createdAt',default=now_ms)
        stop=self._num(row,'stopLossPrice','stopLoss','presetStopLossPrice')
        tp2=self._num(row,'takeProfitPrice','takeProfit','presetStopSurplusPrice')
        base_r=max(entry*.0025,1e-9)
        if stop<=0:
            stop=entry-base_r if side=='LONG' else entry+base_r
        initial_r=max(abs(entry-stop),base_r)
        if tp2<=0:
            tp2=entry+initial_r*1.8 if side=='LONG' else entry-initial_r*1.8
        tp1=entry+initial_r*1.35 if side=='LONG' else entry-initial_r*1.35
        p=ManagedPosition(sym,side,qty,entry,stop,tp1,tp2,initial_r,opened,
                          entry_regime='RECOVERED')
        self.managed_positions[sym]=p
        age=max(0,(now_ms-opened)/60000)
        print(f"POSITION_TRACKED {sym} side={side} qty={qty} entry={entry} age_min={age:.1f}",flush=True)
        return p

    def _submit_classic_close(self,sym:str,p:ManagedPosition,row:dict,reason:str,
                              mark:float,qty_fraction:float=1.0):
        now_ms=int(time.time()*1000)
        full=qty_fraction>=.999
        if full:
            inflight=self.position_exit_inflight.get(sym)
            if inflight and now_ms-int(inflight.get('submitted_ms') or 0)<15_000:
                return True
        qty=max(0.0,p.qty*max(0.0,min(1.0,float(qty_fraction))))
        qty=normalize_qty(qty,self.instruments.get(sym,{}) or {})
        if qty<=0:
            qty=normalize_qty(p.qty,self.instruments.get(sym,{}) or {})
        if qty<=0:
            print(f"POSITION_EXIT_REJECTED {sym} reason=invalid close quantity",flush=True)
            return False
        hold=str(row.get('holdSide') or '').lower()
        margin_coin=str(row.get('marginCoin') or self.demo_margin_coin or 'USDT')
        oid=f"RUD-X-{sym}-{now_ms}-{uuid.uuid4().hex[:5]}"
        mode=str(self.account_hold_mode or '').lower()
        if 'hedge' in mode or hold in ('long','short'):
            body={
                'symbol':sym,'productType':'USDT-FUTURES','marginMode':'crossed',
                'marginCoin':margin_coin,'size':format(qty,'.12g'),
                'side':'buy' if hold=='long' else 'sell',
                'tradeSide':'close','orderType':'market','force':'gtc','clientOid':oid,
            }
        else:
            side='sell' if p.side=='LONG' else 'buy'
            body={
                'symbol':sym,'productType':'USDT-FUTURES','marginMode':'crossed',
                'marginCoin':margin_coin,'size':format(qty,'.12g'),
                'side':side,'orderType':'market','force':'gtc','reduceOnly':'YES',
                'clientOid':oid,
            }
        try:
            ack=self.rest.classic_place_order(body)
            self.exec.record_external_ack(body,ack)
        except Exception as exc:
            self.safety.record_order_reject(str(exc))
            print(f"POSITION_EXIT_REJECTED {sym} reason={str(exc)[:240]}",flush=True)
            return False
        self.safety.clear_order_rejects()
        if full:
            self.position_exit_inflight[sym]={
                'submitted_ms':now_ms,'reason':reason,'mark':mark,'qty':qty,
                'ack_code':ack.get('code')
            }
            print(f"POSITION_EXIT_SUBMITTED {sym} side={p.side} qty={qty} reason={reason} mark={mark}",flush=True)
        else:
            p.qty=max(0.0,p.qty-qty)
            print(f"POSITION_PARTIAL_EXIT_SUBMITTED {sym} qty={qty} reason={reason} mark={mark}",flush=True)
        return True

    def _reconcile_classic_position(self,sym:str,mark:float=0.0):
        if self.execution_backend!='CLASSIC_V2_DEMO':
            return None
        now_ms=int(time.time()*1000)
        row=self._classic_position_active(sym)
        if row is not None:
            p=self._adopt_managed_position(sym,row,mark,now_ms)
            inflight=self.position_exit_inflight.get(sym)
            if inflight and now_ms-int(inflight.get('submitted_ms') or 0)>=15_000:
                print(f"POSITION_EXIT_STILL_OPEN {sym} retry_allowed=true",flush=True)
                self.position_exit_inflight.pop(sym,None)
                inflight=None
            # Recovery-safe time stop: after a restart, an already-stale scalp
            # must not wait for the next candle before being managed.
            if (p is not None and mark>0 and not inflight
                    and now_ms-p.opened_ms>=self.posmgr.max_hold_ms):
                self._submit_classic_close(sym,p,row,'TIME_EXIT_45M_RECOVERY',mark,1.0)
            return p

        p=self.managed_positions.get(sym)
        if p is None:
            return None
        anyrow=self._classic_position_any(sym) or {}
        inflight=self.position_exit_inflight.pop(sym,None)
        reason=(inflight or {}).get('reason') or 'EXCHANGE_TP_SL_OR_EXTERNAL'
        exit_price=float((inflight or {}).get('mark') or mark or
                         self._num(anyrow,'markPrice','marketPrice','closePrice',default=p.entry))
        gross=(exit_price-p.entry)*p.qty if p.side=='LONG' else (p.entry-exit_price)*p.qty
        realized=self._num(anyrow,'achievedProfits','realizedPL','realizedPnl','realizedPnlAfterFee',default=0.0)
        pnl_text=f"realized={realized:.6f}" if abs(realized)>1e-12 else f"estimated_gross={gross:.6f}"
        print(f"POSITION_CLOSED {sym} side={p.side} qty={p.qty} reason={reason} exit={exit_price} {pnl_text}",flush=True)
        try:
            self.journal.log_trade(
                trade_id=f"{sym}-{p.opened_ms}",symbol=sym,side=p.side,
                opened_ms=p.opened_ms,closed_ms=now_ms,entry=p.entry,exit=exit_price,
                qty=p.qty,gross_pnl=gross,fees=None,funding=None,slippage=None,
                net_pnl=realized if abs(realized)>1e-12 else None,
                exit_reason=reason,decision_id=None,
            )
        except Exception as exc:
            print(f"POSITION_JOURNAL_WARNING {sym} reason={str(exc)[:160]}",flush=True)
        self.managed_positions.pop(sym,None)
        return None

    def _health_payload(self, equity:float)->dict:
        positions=[]
        for (symbol,side),row in self.exec.state.positions.items():
            try: size=float(row.get('size') or row.get('qty') or 0)
            except Exception: size=0.0
            if size>0:
                positions.append({'symbol':symbol,'side':str(side).upper(),'size':size})
        if self.execution_backend=='CLASSIC_V2_DEMO':
            positions=[]
            for row in self.classic_positions:
                try: size=float(row.get('total') or row.get('available') or 0)
                except Exception: size=0.0
                if size>0: positions.append({'symbol':row.get('symbol'),'side':str(row.get('holdSide') or 'net').upper(),'size':size})
        perm_known=bool(self.account_perm_type or self.account_permissions)
        trade_permission=(self.account_perm_type=='read-and-write' and 'uta_trade' in set(self.account_permissions)) if perm_known else None
        if equity>0:
            account_status='READY'
        elif trade_permission is False:
            account_status='API_PERMISSION_BLOCK'
        else:
            account_status='WAITING_FOR_DEMO_FUNDS'
        return {
            'status':'running',
            'mode':'DEMO',
            'private_ws':self.pws.logged_in,
            'execution_backend':self.execution_backend,
            'demo_margin_coin':self.demo_margin_coin,
            'account_status':account_status,
            'funding_required':equity<=0,
            'trade_permission_ok':trade_permission,
            'account_mode':self.account_mode,
            'account_level':self.account_level,
            'hold_mode':self.account_hold_mode,
            'uta_assets':self.uta_asset_snapshot,
            'classic_accounts':self.classic_account_snapshot,
            'account_meta_error':self.account_meta_error,
            'account_asset_error':self.account_asset_error,
            'classic_account_error':self.classic_account_error,
            'target_leverage':self.target_leverage,
            'leverage_ready':self.leverage_ready,
            'leverage_verified':self.leverage_verified,
            'leverage_error':self.leverage_error,
            'legacy_sim_error':'disabled: unsupported legacy synthetic route',
            'equity':equity,
            'symbols':list(self.symbols),
            'signals':{sym:self.state[sym].last_decision for sym in self.symbols},
            'open_positions':positions,
            'orders_seen':len(self.exec.state.orders),
            'fills_seen':len(self.exec.state.fills),
            'position_management':{
                sym:{
                    'side':p.side,'qty':p.qty,'entry':p.entry,'stop':p.stop,
                    'tp1':p.tp1,'tp2':p.tp2,'peak_r':round(p.peak_r,4),
                    'age_min':round(max(0,(int(time.time()*1000)-p.opened_ms)/60000),2),
                    'entry_regime':p.entry_regime,
                    'exit_inflight':sym in self.position_exit_inflight,
                } for sym,p in self.managed_positions.items()
            },
            'news_signed_score':self.news_engine.last.get('signed_score',0),
            'news_errors':self.news_collector.errors,
            'ts_ms':int(time.time()*1000),
        }

    async def prewarm(self):
        for sym in self.symbols:
            ins=self.rest.instruments(sym).get('data') or []
            if not ins or ins[0].get('status')!='online': raise RuntimeError(f'{sym} not online')
            self.instruments[sym]=ins[0]
            rows=self.rest.candles(sym,'1m',limit=300).get('data') or []
            for row in sorted(rows,key=lambda x:int(x[0])):
                _,o,h,l,c,v,*_=row
                vals=tuple(map(float,(o,h,l,c,v)))
                self.state[sym].engine.update_candle(*vals)
                self.state[sym].mtf.update_1m(*vals)
            for interval,method in [('5m',self.state[sym].mtf.update_5m),('15m',self.state[sym].mtf.update_15m)]:
                tfrows=self.rest.candles(sym,interval,limit=300).get('data') or []
                for row in sorted(tfrows,key=lambda x:int(x[0])):
                    _,o,h,l,c,v,*_=row; method(*map(float,(o,h,l,c,v)))

    async def run(self,public_ws,seconds=3600):
        await self.prewarm()
        self._refresh_account_meta(force=True)
        eq=self._equity_from_private(force=True); self.day_start_equity=eq if eq>0 else 0.0; self.equity_peak=eq if eq>0 else 0.0
        if eq>0:
            self._configure_demo_leverage(force=True)
        private_task=asyncio.create_task(self.pws.run(self._private_message))
        public_task=asyncio.create_task(public_ws.run_once(seconds))
        news_task=asyncio.create_task(self._news_loop())
        start=time.monotonic()
        try:
            while time.monotonic()-start < seconds:
                await asyncio.sleep(.25)
                if private_task is not None and private_task.done():
                    exc=private_task.exception()
                    raise RuntimeError(f'private websocket stopped: {exc}')
                if public_task.done() and time.monotonic()-start < seconds-1:
                    exc=public_task.exception()
                    raise RuntimeError(f'public websocket stopped: {exc}')
                eq=self._equity_from_private()
                self._sync_classic_positions()
                if eq>0:
                    self._configure_demo_leverage()
                if eq>0 and (not self.day_start_equity or self.day_start_equity<=0): self.day_start_equity=eq
                if eq>0: self.equity_peak=max(self.equity_peak or eq,eq)
                for sym in self.symbols:
                    st=public_ws.states[sym]
                    rs=self.state[sym]
                    mark_now=((float(st.bid)+float(st.ask))/2.0) if st.bid and st.ask else float(st.bid or st.ask or 0)
                    if self.execution_backend=='CLASSIC_V2_DEMO':
                        self._reconcile_classic_position(sym,mark_now)
                    for tf,last_seen_attr,last_proc_attr,method in [
                        ('5m','last_seen_5m_ts','last_processed_5m_ts',rs.mtf.update_5m),
                        ('15m','last_seen_15m_ts','last_processed_15m_ts',rs.mtf.update_15m)]:
                        trows=st.candles[tf]
                        if trows:
                            cur=int(trows[-1][0]); last_seen=getattr(rs,last_seen_attr)
                            if last_seen==0: setattr(rs,last_seen_attr,cur)
                            elif cur!=last_seen and len(trows)>=2:
                                setattr(rs,last_seen_attr,cur); prevtf=trows[-2]; pts_tf=int(prevtf[0])
                                if pts_tf>getattr(rs,last_proc_attr):
                                    _,oo,hh,ll,cc,vv,*_=prevtf; method(*map(float,(oo,hh,ll,cc,vv))); setattr(rs,last_proc_attr,pts_tf)
                    rows=st.candles['1m']
                    if not rows: continue
                    row=rows[-1]
                    # Use a candle only once. Signals are built on completed bars; live current bar is ignored until timestamp changes.
                    try: ts=int(row[0])
                    except Exception: continue
                    if rs.last_seen_open_ts==0:
                        rs.last_seen_open_ts=ts; continue
                    if ts==rs.last_seen_open_ts: continue
                    # A new candle opened, so the prior cached candle is now closed.
                    prev=rows[-2] if len(rows)>=2 else None
                    rs.last_seen_open_ts=ts
                    if not prev: continue
                    pts,po,ph,pl,pc,pv,*_=prev
                    pts=int(pts)
                    if pts<=rs.last_processed_closed_ts: continue
                    rs.last_processed_closed_ts=pts
                    o,h,l,c,v=map(float,(po,ph,pl,pc,pv))
                    scores=rs.engine.update_candle(o,h,l,c,v,book=st.books5,trades=st.trades,bid=st.bid,ask=st.ask,funding_rate=st.funding_rate,open_interest=st.open_interest)
                    rs.mtf.update_1m(o,h,l,c,v)
                    scores['trend']=rs.mtf.score()
                    depth=0.0
                    if st.books5:
                        for side in ('b','a'):
                            for z in (st.books5.get(side) or [])[:5]:
                                try: depth += float(z[0])*float(z[1])
                                except Exception: pass
                    vs=rs.vol.update(h,l,c,st.bid,st.ask,depth)
                    ns=self.news_score
                    scores['volatility_execution']=vs; scores['news_macro']=ns
                    co=consensus(scores)
                    adx=rs.mtf.last.get('adx5') or rs.engine.trend.last.get('adx',0); bbw=rs.vol.last.get('bb_width_pct',0)
                    br=bool(rs.engine.structure.last.get('breakout_up') or rs.engine.structure.last.get('breakout_down'))
                    regime=rs.regime.update(c,rs.vol.last.get('atr',0),adx,st.spread_pct,bbw,br,depth)
                    dl=(self.day_start_equity-eq)/self.day_start_equity*100 if self.day_start_equity else 0
                    dd=(self.equity_peak-eq)/self.equity_peak*100 if self.equity_peak else 0
                    now_ms=int(time.time()*1000)
                    safe=self.safety.evaluate(now_ms=now_ms,last_market_ms=st.last_update_ms,spread_pct=st.spread_pct,expected_slippage_pct=None,ws_connected=public_ws is not None and not st.is_stale(),account_synced=(self.pws.logged_in if self.execution_backend=='UTA_V3_DEMO' else (int(time.time()*1000)-self.classic_last_ok_ms<5000)),equity_ok=eq>0,daily_loss_hit=dl>=self.risk.max_daily_loss_pct,drawdown_hit=dd>=self.risk.max_drawdown_pct)
                    candle_ret=(c/o-1)*100 if o else 0.0
                    bcheck=self.breaking.evaluate(now_ms,candle_ret,scores['order_flow'].direction)
                    cooldown=(now_ms-rs.last_entry_ms)<120_000 if rs.last_entry_ms else False
                    entry_risk_allow=safe.allow_new_entries and self.leverage_ready
                    ed=self.entry.decide(co,regime,breaking_allow=bcheck['allow'],risk_allow=entry_risk_allow,cooldown=cooldown)
                    normal_reason=ed.reason
                    fast_ed=None
                    if not ed.enter:
                        candle_range=(h-l)/c*100 if c else 0.0
                        fast_ed=self.entry.decide_directional_core(
                            co,scores,regime,candle_ret_pct=candle_ret,candle_range_pct=candle_range,
                            atr_pct=rs.vol.last.get('atr_pct',0),spread_pct=st.spread_pct,
                            depth_notional=depth,mtf5=rs.mtf.last.get('5m','NEUTRAL'),
                            mtf15=rs.mtf.last.get('15m','NEUTRAL'),
                            breakout_up=bool(rs.engine.structure.last.get('breakout_up')),
                            breakout_down=bool(rs.engine.structure.last.get('breakout_down')),
                            breaking_allow=bcheck['allow'],risk_allow=entry_risk_allow,
                            cooldown=cooldown)
                        if fast_ed.enter:
                            ed=fast_ed
                    fam={k:{'long':round(x.long,3),'short':round(x.short,3),'direction':x.direction,'confidence':round(x.confidence,3),'veto':x.veto,'reason':x.reason} for k,x in scores.items()}
                    snapshot={
                        'closed_candle_ts_ms':pts,
                        'updated_ts_ms':now_ms,
                        'price':c,
                        'regime':regime,
                        'consensus':co.direction,
                        'long_score':co.long_score,
                        'short_score':co.short_score,
                        'actual_score':ed.actual_score,
                        'required_score':ed.required_score,
                        'aligned_families':co.aligned_families,
                        'minimum_aligned_families':self.entry.min_aligned,
                        'entry_approved':ed.enter,
                        'status':'ENTRY_APPROVED' if ed.enter else 'HOLD',
                        'reason':ed.reason,
                        'safety_allow':safe.allow_new_entries,
                        'safety_reasons':list(safe.reasons),
                        'breaking_allow':bcheck['allow'],
                        'breaking_reason':bcheck['reason'],
                        'cooldown':cooldown,
                        'spread_pct':st.spread_pct,
                        'depth_notional':round(depth,2),
                        'candle_return_pct':round(candle_ret,4),
                        'normal_entry_reason':normal_reason,
                        'directional_core_reason':fast_ed.reason if fast_ed is not None else '',
                        'private_ws':self.pws.logged_in,
                        'target_leverage':self.target_leverage,
                        'leverage_ready':self.leverage_ready,
                        'leverage_error':self.leverage_error,
                        'families':fam,
                    }
                    rs.last_decision=snapshot
                    print(
                        f"SIGNAL {sym} {co.direction} score={ed.actual_score:.2f}/{ed.required_score:.2f} "
                        f"aligned={co.aligned_families}/{self.entry.min_aligned} regime={regime} "
                        f"status={snapshot['status']} reason={snapshot['reason']}",
                        flush=True,
                    )
                    did=self.journal.log_decision(ts_ms=pts,symbol=sym,regime=regime,side=co.direction,composite=max(co.long_score,co.short_score),aligned=co.aligned_families,news=self.news_engine.last.get('signed_score',0),families=fam,reason=ed.reason,entered=False)

                    # Manage an existing Classic Demo position on every completed
                    # 1m bar. Single 1m noise cannot close it; PositionManager
                    # requires confirmed reversal/failed breakout/profit giveback,
                    # the 45m time stop, or the account kill switch.
                    if self.execution_backend=='CLASSIC_V2_DEMO':
                        prow=self._classic_position_active(sym)
                        p=self._reconcile_classic_position(sym,c)
                        if prow is not None and p is not None:
                            kill_switch=(dl>=self.risk.max_daily_loss_pct or dd>=self.risk.max_drawdown_pct)
                            action=self.posmgr.update(
                                p,c,now_ms,rs.vol.last.get('atr',0),
                                consensus_direction=co.direction,
                                long_score=co.long_score,short_score=co.short_score,
                                aligned_families=co.aligned_families,
                                mtf1=rs.mtf.last.get('1m','NEUTRAL'),
                                mtf5=rs.mtf.last.get('5m','NEUTRAL'),
                                mtf15=rs.mtf.last.get('15m','NEUTRAL'),
                                structure_direction=scores['structure_fibonacci'].direction,
                                momentum_direction=scores['momentum'].direction,
                                kill_switch=kill_switch,
                            )
                            snapshot['position_action']=action.action
                            snapshot['position_action_reason']=action.reason
                            snapshot['managed_peak_r']=round(p.peak_r,4)
                            if action.action=='CLOSE':
                                ok=self._submit_classic_close(sym,p,prow,action.reason,c,1.0)
                                snapshot['status']='EXIT_SUBMITTED' if ok else 'EXIT_REJECTED'
                                snapshot['reason']=action.reason
                                rs.last_decision=snapshot
                                continue
                            if action.action=='PARTIAL_CLOSE':
                                ok=self._submit_classic_close(sym,p,prow,action.reason,c,action.qty_fraction)
                                snapshot['status']='PARTIAL_EXIT_SUBMITTED' if ok else 'PARTIAL_EXIT_REJECTED'
                                snapshot['reason']=action.reason
                                rs.last_decision=snapshot
                                continue
                            if action.action=='MOVE_STOP':
                                # This is a bot-side soft stop. The original
                                # exchange SL remains attached as crash protection.
                                print(f"POSITION_SOFT_STOP {sym} stop={p.stop} reason={action.reason}",flush=True)
                                snapshot['status']='POSITION_MANAGED'
                                snapshot['reason']=action.reason
                                rs.last_decision=snapshot
                                continue
                    if not ed.enter: continue
                    # Never stack the same market. Use the active backend's
                    # authoritative position state.
                    if self.execution_backend=='CLASSIC_V2_DEMO':
                        existing=any(self._same_market(x.get('symbol'),sym) and float(x.get('total') or x.get('available') or 0)>0 for x in self.classic_positions)
                    else:
                        existing=any(self._same_market(k[0],sym) and float(v.get('size') or v.get('qty') or 0)>0 for k,v in self.exec.state.positions.items())
                    if existing:
                        snapshot['status']='BLOCKED'; snapshot['reason']='existing position on symbol'
                        print(f"BLOCK {sym} reason={snapshot['reason']}",flush=True)
                        continue
                    fib=rs.engine.structure.last
                    ext=(fib.get('extensions') or {}).get('127.2')
                    side=ed.side
                    plan=self.exits.plan(side,c,rs.vol.last.get('atr',0),fib.get('swing_low'),fib.get('swing_high'),ext)
                    if self.execution_backend=='CLASSIC_V2_DEMO':
                        current_pos=[{'symbol':x.get('symbol'),'side':str(x.get('holdSide') or 'net').upper()} for x in self.classic_positions if float(x.get('total') or x.get('available') or 0)>0]
                    else:
                        current_pos=[{'symbol':k[0],'side':str(k[1]).upper()} for k,v in self.exec.state.positions.items() if float(v.get('size') or v.get('qty') or 0)>0]
                    rd=self.risk.assess(eq,self.day_start_equity,self.equity_peak,c,plan.stop,side,current_pos,5)
                    snapshot['risk_allow']=rd.allow; snapshot['risk_reason']=rd.reason; snapshot['risk_usdt']=round(rd.risk_usdt,6)
                    if not rd.allow:
                        snapshot['status']='BLOCKED'; snapshot['reason']=f"risk: {rd.reason}"
                        print(f"BLOCK {sym} reason={snapshot['reason']}",flush=True)
                        continue
                    qty_ins=self.instruments[sym]
                    qty=normalize_qty(rd.qty,qty_ins)
                    tp1_price=normalize_price(plan.tp1,qty_ins)
                    tp_price=normalize_price(plan.tp2,qty_ins)
                    sl_price=normalize_price(plan.stop,qty_ins)
                    min_amt=float(qty_ins.get('minOrderAmount') or qty_ins.get('minTradeUSDT') or 0)
                    snapshot['planned_qty']=qty; snapshot['planned_notional']=round(qty*c,6)
                    if qty<=0 or qty*c < min_amt:
                        snapshot['status']='BLOCKED'; snapshot['reason']='normalized quantity below exchange minimum'
                        print(f"BLOCK {sym} reason={snapshot['reason']} qty={qty}",flush=True)
                        continue
                    order_side='buy' if side=='LONG' else 'sell'
                    try:
                        if self.execution_backend=='CLASSIC_V2_DEMO':
                            base_oid=f'RUD-{sym}-{pts}'
                            last_exc=None; ack=None; body=None
                            for api_symbol in (sym,self._demo_display_symbol(sym)):
                                try:
                                    body=self.exec.build_classic_order(api_symbol,order_side,qty,order_type='market',oid=base_oid,margin_coin=self.demo_margin_coin,take_profit=tp_price,stop_loss=sl_price)
                                    ack=self.rest.classic_place_order(body)
                                    self.exec.record_external_ack(body,ack)
                                    break
                                except Exception as exc:
                                    last_exc=exc
                                    continue
                            if ack is None: raise last_exc or RuntimeError('Classic demo order failed')
                        else:
                            body=self.exec.build_order(sym,order_side,qty,order_type='market',oid=f'RUD-{sym}-{pts}',take_profit=plan.tp2,stop_loss=plan.stop)
                            ack=self.exec.place_order(body)
                    except Exception as exc:
                        self.safety.record_order_reject(str(exc))
                        snapshot['status']='ORDER_REJECTED'; snapshot['reason']=str(exc)[:240]
                        print(f"ORDER_REJECTED {sym} reason={snapshot['reason']}",flush=True)
                        continue
                    self.safety.clear_order_rejects()
                    rs.last_entry_ms=now_ms
                    self.managed_positions[sym]=ManagedPosition(
                        symbol=sym,side=side,qty=qty,entry=c,stop=sl_price,
                        tp1=tp1_price,tp2=tp_price,initial_r=max(abs(c-sl_price),c*.0025),
                        opened_ms=now_ms,entry_regime=regime,
                    )
                    self.position_exit_inflight.pop(sym,None)
                    snapshot.update({
                        'status':'ORDER_SUBMITTED',
                        'reason':'demo market order accepted; awaiting private WS reconciliation',
                        'side':side,
                        'client_oid':body['clientOid'],
                        'qty':qty,
                        'stop_loss':sl_price,
                        'take_profit_1':tp1_price,
                        'take_profit':tp_price,
                        'order_ack_code':ack.get('code'),
                        'execution_backend':self.execution_backend,
                        'api_symbol':body.get('symbol'),
                    })
                    print(f"ORDER_SUBMITTED {sym} side={side} qty={qty} oid={body['clientOid']}",flush=True)
                    self.journal.db.execute('UPDATE decisions SET entered=1 WHERE id=?',(did,)); self.journal.db.commit()
                self.health.write(self._health_payload(eq))
        finally:
            self.pws.stop();
            if private_task is not None: private_task.cancel()
            public_task.cancel(); news_task.cancel(); self.journal.close()
