import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rudrila.ws_public import BitgetPublicDemoWS,_normalize_kline_row
from rudrila.settings import BitgetSettings

class KlineV3Tests(unittest.TestCase):
    def setUp(self):
        os.environ['RUDRILA_MODE']='demo'; os.environ['LIVE_TRADING']='false'

    def test_normalize_uta_object(self):
        row=_normalize_kline_row({'start':'1710518400000','open':'276670','high':'400005','low':'276670','close':'400005','volume':'0.423','turnover':'148190.38375'})
        self.assertEqual(row,['1710518400000','276670','400005','276670','400005','0.423','148190.38375'])

    def test_kline_updates_replace_same_open_candle(self):
        w=BitgetPublicDemoWS(BitgetSettings.from_env(),symbols=('BTCUSDT',))
        base={'arg':{'symbol':'BTCUSDT','topic':'kline','interval':'1m'},'ts':1}
        m=dict(base); m['data']=[{'start':'1000','open':'100','high':'101','low':'99','close':'100.5','volume':'1','turnover':'100'}]
        w.handle(m)
        m2=dict(base); m2['data']=[{'start':'1000','open':'100','high':'102','low':'99','close':'101.5','volume':'2','turnover':'201'}]
        w.handle(m2)
        self.assertEqual(len(w.states['BTCUSDT'].candles['1m']),1)
        self.assertEqual(w.states['BTCUSDT'].candles['1m'][-1][4],'101.5')
        m3=dict(base); m3['data']=[{'start':'2000','open':'101.5','high':'103','low':'101','close':'102','volume':'1','turnover':'102'}]
        w.handle(m3)
        self.assertEqual(len(w.states['BTCUSDT'].candles['1m']),2)

    def test_missing_volume_defaults_zero(self):
        row=_normalize_kline_row({'start':'1','open':'1','high':'2','low':'1','close':'2'})
        self.assertEqual(row[5:7],['0','0'])

if __name__=='__main__': unittest.main()
