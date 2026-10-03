import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from rudrila.dashboard import render_dashboard

class MonitoringDashboardTests(unittest.TestCase):
    def test_render_rejection_reason_and_family(self):
        data={
          'status':'running','private_ws':True,'equity':1000,'symbols':['BTCUSDT'],
          'signals':{'BTCUSDT':{
            'status':'HOLD','consensus':'LONG','actual_score':71.2,'required_score':80.0,
            'aligned_families':4,'minimum_aligned_families':5,'regime':'TREND','price':65000,
            'reason':'not enough independent families; score below threshold','safety_allow':False,'safety_reasons':['no positive demo equity'],
            'breaking_reason':'no breaking-news lock','spread_pct':0.01,
            'families':{'order_flow':{'direction':'LONG','long':80,'short':10,'confidence':80,'veto':False}}
          }}
        }
        out=render_dashboard(data)
        self.assertIn('score below threshold',out)
        self.assertIn('order_flow',out)
        self.assertIn('71.2 / 80.0',out)
        self.assertIn('Real money remains OFF',out)
        self.assertIn('no positive demo equity',out)

if __name__=='__main__': unittest.main()
