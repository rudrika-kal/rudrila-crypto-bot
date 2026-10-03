from __future__ import annotations
import time
from .rest_client import BitgetREST

class Preflight:
    def __init__(self,rest:BitgetREST,symbols=('BTCUSDT','ETHUSDT')):
        self.rest=rest; self.symbols=symbols
    def run_public(self):
        checks={}; details={}
        try:
            st=self.rest.server_time(); server=int(st['data']['serverTime']); local=int(time.time()*1000)
            drift=abs(server-local); checks['server_time']=drift<20_000; details['clock_drift_ms']=drift
        except Exception as e: checks['server_time']=False; details['server_time_error']=str(e)
        for sym in self.symbols:
            try:
                data=self.rest.instruments(sym).get('data') or []
                ins=data[0] if data else {}
                checks[f'{sym}_online']=ins.get('status')=='online'
                details[f'{sym}_instrument']=ins
            except Exception as e: checks[f'{sym}_online']=False; details[f'{sym}_error']=str(e)
        return {'pass':all(checks.values()),'checks':checks,'details':details}
    def run_private(self):
        checks={}; details={}
        info=self.rest.account_info().get('data') or {}
        perms=set(info.get('permissions') or [])
        checks['uta_trade_permission']='uta_trade' in perms
        checks['withdraw_permission_off']='withdraw' not in perms
        checks['read_write']=info.get('permType')=='read-and-write'
        settings=self.rest.account_settings().get('data') or {}
        checks['one_way_mode']=settings.get('holdMode')=='one_way_mode'
        details['permissions']=sorted(perms); details['holdMode']=settings.get('holdMode')
        assets=self.rest.account_assets().get('data') or []
        details['asset_rows']=len(assets) if isinstance(assets,list) else 1
        return {'pass':all(checks.values()),'checks':checks,'details':details}
