import hashlib
import os
from pathlib import Path
import sys
import unittest
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from changes import material_changes
from market_session import mobile_schedule
from projection import project, select_report

TOKEN='test-access-code-with-enough-entropy'


class Repository:
    def snapshot(self): return {'schema_version':1,'stocks':[{'symbol':'RKLB'}]}
    def report(self,symbol): return {'symbol':symbol} if symbol=='RKLB' else None


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ACCESS_TOKEN_SHA256':hashlib.sha256(TOKEN.encode()).hexdigest()}); self.env.start()
        self.client=create_app(Repository()).test_client()
    def tearDown(self): self.env.stop()
    def test_authentication_and_no_store(self):
        self.assertEqual(self.client.get('/health').status_code,200)
        self.assertEqual(self.client.get('/v1/dashboard').status_code,401)
        self.assertEqual(self.client.get('/v1/dashboard',headers={'Authorization':'Bearer incorrect-secret-not-valid'}).status_code,401)
        response=self.client.get('/v1/dashboard',headers={'Authorization':f'Bearer {TOKEN}'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_reports_and_methods(self):
        headers={'Authorization':f'Bearer {TOKEN}'}
        self.assertEqual(self.client.get('/v1/reports/RKLB',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/v1/reports/UNKNOWN',headers=headers).status_code,404)
        self.assertEqual(self.client.post('/v1/dashboard',headers=headers).status_code,405)
    def test_failed_attempt_preserves_old_report_date(self):
        latest={'analysis_status':'failed','generated_at':'2026-09-30'}
        mirror={'analysis_status':'ok','generated_at':'2026-09-29'}
        report,status=select_report(latest,mirror)
        self.assertEqual(report['generated_at'],'2026-09-29')
        self.assertEqual(status,'failed')
    def test_projection_nulls_not_zero_and_changes(self):
        layout={'blocks':[],'groups':[{'id':'space','label':'Espacio','benchmark':'UFO','tickers':['RKLB']}],'general_panel':{'start_row':2,'column':'A','lines':[]}}
        report={'symbol':'RKLB','analysis_status':'ok','generated_at':'2026-09-29T12:00:00Z','decision':{'score':8,'thesis_score':8,'score_basis':'thesis','setup_score':7},'changes':{'score_change_material':True,'previous_score':7,'score_delta':1,'setup_delta':.5,'new_catalysts':[{'impact':8,'title':'Nuevo contrato'}], 'plan_changes':[{'message':'Entrada nueva'}]},'ibkr_recent_news':{'items':[{'headline':'Noticia','time':'2026-09-29T10:00:00Z','articleId':'a'}]}}
        result=project(layout,{'positions':{'RKLB':2}},{},{},{'RKLB':report},{},[])
        stock=result['stocks'][0]
        self.assertIsNone(stock['price'])
        self.assertIsNone(stock['day_change'])
        self.assertEqual(stock['shots'],2)
        self.assertEqual({item['kind'] for item in result['changes']},{'score','catalyst'})
        self.assertEqual(len(result['news']),1)
    def test_migration_does_not_emit_false_score_change(self):
        layout={'blocks':[],'groups':[{'id':'g','tickers':['X']}],'general_panel':{'start_row':2,'column':'A','lines':[]}}
        report={'analysis_status':'ok','changes':{'score_basis_changed':True,'score_delta':2,'score_change_material':True},'decision':{'score':8}}
        self.assertEqual(project(layout,{}, {},{}, {'X':report},{},[])['changes'],[])
    def test_shared_news_is_not_repeated(self):
        layout={'blocks':[],'groups':[{'id':'g','tickers':['A','B']}],'general_panel':{'start_row':2,'column':'A','lines':[]}}
        report={'analysis_status':'ok','ibkr_recent_news':{'items':[{'articleId':'same','headline':'One article'}]}}
        result=project(layout,{}, {},{}, {'A':report,'B':report},{},[])
        self.assertEqual(len(result['news']),1)
        self.assertEqual(result['news'][0]['symbols'],['A','B'])
    def test_stale_cache_preserves_original_timestamp(self):
        from sources import PublishedSources
        repository=PublishedSources(storage_client=object(),sheets_session=object())
        repository.cached={'generated_at':'2026-09-29T00:00:00Z','warnings':[]}
        with patch.object(repository,'_load',side_effect=RuntimeError('source failure')):
            with self.assertLogs('sources',level='ERROR'):
                payload=repository.snapshot()
        self.assertTrue(payload['stale'])
        self.assertEqual(payload['generated_at'],'2026-09-29T00:00:00Z')

    def test_material_feed_compares_history_and_filters_analysts(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok','thesis_score':7,
                  'catalysts':[{'title':'Contrato NASA','date':'2026-10-15','impact':8},
                               {'title':'Hito regulatorio','date':'2026-11-01','impact':7}],
                  'next_event':{'title':'Resultados Q3','date':'2026-10-20'}}
        report={'generated_at':'2026-09-30T12:00:00Z','decision':{'thesis_score':8,'thesis_reason':'Mejora material'},
                'catalysts':[{'title':'Contrato NASA','date':'2026-10-22','impact':9,'explanation':'Se aplaza una semana'},
                             {'title':'Nuevo contrato','date':'2026-11-10','impact':8}],
                'next_event':{'title':'Resultados Q3','date':'2026-10-25'},
                'analyst_recent_actions':{'status':'ok','actions':[
                    {'event_type':'rating_downgraded','firm':'Firma A','rating':'Hold','published_at':'2026-09-30T10:00:00Z','headline':'Downgrade','articleId':'a'},
                    {'event_type':'rating_maintained','firm':'Firma B','published_at':'2026-09-30T09:00:00Z','headline':'Maintained'},
                    {'event_type':'price_target_raised','firm':'Firma C','target':120,'published_at':'2026-09-30T08:00:00Z','headline':'Price Target Raised to $120 From $100','articleId':'c'},
                    {'event_type':'price_target_raised','firm':'Firma D','target':105,'published_at':'2026-09-30T07:00:00Z','headline':'Price Target Raised to $105 From $100','articleId':'d'},
                ]}}
        changes=material_changes(report,{'entries':[previous,{'generated_at':report['generated_at'],'analysis_status':'ok'}]})
        self.assertEqual([(item['kind'],item['change_type']) for item in changes],
                         [('score','updated'),('catalyst','updated'),('catalyst','new'),('catalyst','removed'),
                          ('event','updated'),('analyst','rating_downgraded'),('analyst','price_target_raised')])
        self.assertIn('no confirma', changes[3]['detail'])
        self.assertEqual(changes[4]['event_date'],'2026-10-25')

    def test_unchanged_event_and_paraphrased_catalyst_do_not_repeat(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok','thesis_score':8,
                  'catalysts':[{'title':'Acuerdo de suministro nuclear','date':'2026-11-01','impact':8,'explanation':'Contrato anunciado'}],
                  'next_event':{'title':'Presentación de resultados','date':'2026-10-20','explanation':'Conferencia'}}
        report={'generated_at':'2026-09-30T12:00:00Z','decision':{'thesis_score':8},
                'catalysts':[{'title':'Acuerdo de suministro nuclear','date':'2026-11-01','impact':8,'explanation':'Contrato publicado'}],
                'next_event':{'title':'Presentación de resultados','date':'2026-10-20','explanation':'Conferencia'}}
        self.assertEqual(material_changes(report,{'entries':[previous]}),[])

    def test_new_event_is_shown_once_and_technical_price_note_is_excluded(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok',
                  'catalysts':[],'next_event':None}
        report={'generated_at':'2026-09-30T12:00:00Z','catalysts':[
                    {'title':'El soporte de $143-$145 sigue bajo presión','date':'2026-10-10','impact':-8}],
                'next_event':{'title':'Decisión de la FDA','date':'2026-10-20','explanation':'Se espera resolución.'}}
        changes=material_changes(report,{'entries':[previous]})
        self.assertEqual([(item['kind'],item['change_type']) for item in changes],[('event','new')])
        previous['next_event']=report['next_event']
        self.assertEqual(material_changes(report,{'entries':[previous]}),[])

    def test_catalyst_amount_change_is_material_without_impact_change(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok',
                  'catalysts':[{'title':'Contrato de $1.5B con NASA','date':'2026-10-20','impact':8}]}
        report={'generated_at':'2026-09-30T12:00:00Z',
                'catalysts':[{'title':'Contrato de $2.0B con NASA','date':'2026-10-20','impact':8}]}
        changes=material_changes(report,{'entries':[previous]})
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]['change_type'],'updated')
        self.assertIn('Titular anterior',changes[0]['detail'])

    def test_catalyst_rephrasing_and_shorter_titles_do_not_create_changes(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok','catalysts':[
            {'title':'[Electron completa la misión 97 y eleva a 18 los lanzamientos](https://example.com/launch)','date':'2026-09-26','impact':7},
            {'title':'[Cierra $4,2B de convertibles con ATM de hasta 35M](https://example.com/financing)','date':'2026-09-22','impact':-8},
            {'title':'[Los accionistas aprueban la adquisición](https://example.com/vote)','date':'2026-09-24','impact':7,
             'explanation':'El 99% votó a favor.'},
            {'title':'[Q2 mantiene la visibilidad de demanda](https://example.com/results)','date':'2026-08-11','impact':7},
            {'title':'[Agosto confirma crecimiento de clientes y actividad](https://example.com/operations)','date':'2026-09-10','impact':8},
        ]}
        report={'generated_at':'2026-09-30T12:00:00Z','catalysts':[
            {'title':'[Electron completa la misión 97](https://example.com/launch)','date':'2026-09-26','impact':7,
             'explanation':'Fueron 18 lanzamientos.'},
            {'title':'[Cierra $4,2B de convertibles con ATM](https://example.com/financing)','date':'2026-09-22','impact':-8},
            {'title':'[Accionistas aprueban la adquisición](https://example.com/vote)','date':'2026-09-24','impact':7,
             'explanation':'La aprobación elimina una condición.'},
            {'title':'[Resultados Q2 con fuerte demanda](https://example.com/results)','date':'2026-08-11','impact':7},
            {'title':'Datos operativos de agosto','date':'2026-09-10','impact':8},
        ]}
        self.assertEqual(material_changes(report,{'entries':[previous]}),[])

    def test_catalyst_status_change_in_title_is_kept(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok','catalysts':[
            {'title':'[FDA mantiene pendiente la decisión](https://example.com/fda)','date':'2026-10-20','impact':8}]}
        report={'generated_at':'2026-09-30T12:00:00Z','catalysts':[
            {'title':'[FDA aprueba la solicitud](https://example.com/fda)','date':'2026-10-20','impact':8}]}
        self.assertEqual([(item['kind'],item['change_type']) for item in material_changes(report,{'entries':[previous]})],
                         [('catalyst','updated')])

    def test_old_fact_first_added_to_report_is_not_recent_news(self):
        previous={'generated_at':'2026-09-29T12:00:00Z','analysis_status':'ok','catalysts':[]}
        report={'generated_at':'2026-09-30T12:00:00Z','catalysts':[
            {'title':'Acuerdo anunciado hace tres semanas','date':'2026-09-08','impact':8},
            {'title':'Nuevo contrato de ayer','date':'2026-09-29','impact':8}]}
        changes=material_changes(report,{'entries':[previous]})
        self.assertEqual([item['title'] for item in changes],['Nuevo contrato de ayer'])

    def test_mobile_poll_matches_mercado_and_wakes_at_session_change(self):
        from zoneinfo import ZoneInfo
        ny=ZoneInfo('America/New_York')
        layout={'data_refresh':{'session_intervals_minutes':{'regular':1,'pre-market':5,'post-market':5,'closed':60}}}
        cases=[
            (datetime(2026,10,1,10,0,tzinfo=ny),'regular',60),
            (datetime(2026,10,1,5,0,tzinfo=ny),'pre-market',300),
            (datetime(2026,10,1,17,0,tzinfo=ny),'post-market',300),
            (datetime(2026,10,4,12,0,tzinfo=ny),'closed',3600),
            (datetime(2026,9,7,12,0,tzinfo=ny),'closed',3600),
        ]
        for now,name,seconds in cases:
            with self.subTest(now=now):
                actual=mobile_schedule(layout,now)
                self.assertEqual(actual['session'],name)
                self.assertEqual(actual['poll_after_seconds'],seconds)
        before_open=mobile_schedule(layout,datetime(2026,10,1,9,29,50,tzinfo=ny))
        self.assertEqual(before_open['poll_after_seconds'],15)
        self.assertEqual(before_open['session'],'pre-market')
        changed={'data_refresh':{'session_intervals_minutes':{'regular':2}}}
        self.assertEqual(mobile_schedule(changed,datetime(2026,10,1,10,0,tzinfo=ny))['poll_after_seconds'],120)
        self.assertIsNone(mobile_schedule({},datetime(2026,10,1,10,0,tzinfo=ny))['poll_after_seconds'])


if __name__=='__main__': unittest.main()
