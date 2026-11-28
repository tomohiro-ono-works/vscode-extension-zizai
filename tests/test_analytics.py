import numpy as np
import pandas as pd
import pytest
from connectors.statistics import statistics_connector as st
from connectors.machine_learning import machine_learning_connector as ml

@pytest.fixture
def data():
    rng=np.random.default_rng(12)
    d=pd.DataFrame({'group':np.repeat(np.arange(12),5),'a':rng.normal(size=60),'b':rng.normal(size=60),'category':np.tile(['A','B','A','B','A'],12)})
    d['y']=2*d.a-0.5*d.b+3
    d['accepted']=(d.groupby('group').y.rank(ascending=False)==1).astype(int)
    return d

@pytest.mark.parametrize('action,kwargs',[(st.describe,{}),(st.distribution,{'bins':4}),(st.correlation,{}),(st.multicollinearity,{}),(st.compare_groups,{'group_columns':['category']})])
def test_stats(data,action,kwargs):
    original=data.copy()
    assert len(action(data,columns=['a','b'],**kwargs))>0
    pd.testing.assert_frame_equal(data,original)

@pytest.mark.parametrize('action',[st.hypothesis_test,st.effect_size])
def test_group_tests(data,action):
    assert len(action(data,column='a',group_column='category',group_a='A',group_b='B'))==1

def test_regression(data):
    m=ml.fit_linear_regression(data,features=['a','b'],target='y')
    p=ml.predict(data,model=m)
    assert np.allclose(p.score,data.y)
    assert np.allclose(ml.inspect_model(m).coefficient,[2,-.5])
    assert ml.evaluate_regression(p,target='y').set_index('metric').loc['mae','value']<1e-10

@pytest.mark.parametrize('fit',[ml.fit_logistic_regression,ml.fit_decision_tree,ml.fit_random_forest])
def test_classification(data,fit):
    kw={} if fit==ml.fit_logistic_regression else {'task':'classification'}
    m=fit(data,features=['a','b'],target='accepted',categories=['category'],interactions=True,**kw)
    assert len(m.feature_names)==5
    p=ml.predict(data,model=m)
    assert p.score.between(0,1).all()
    assert len(ml.evaluate_classification(p,target='accepted'))==6

@pytest.mark.parametrize('fit',[ml.fit_pairwise_ranking,ml.fit_lambdamart])
def test_rankers(data,fit):
    m=fit(data,features=['a','b'],target='accepted',group_column='group')
    p=ml.predict(data,model=m,group_column='group')
    assert len(p)==len(data)
    assert p.groupby('group')['rank'].min().eq(1).all()

def test_ranking():
    d=pd.DataFrame({'g':[1,1,2,2,2],'y':[1,0,0,1,0],'score':[5,1,5,4,3]})
    r=ml.evaluate_ranking(d,target='y',group_column='g',k=2,custom_metrics={'combined':lambda d,m:.5*m['hit@1']+.5*m['mrr']})
    m=r['metrics_df'].set_index('metric').value
    assert m['hit@1']==.5 and m['hit@2']==1 and m['mrr']==.75 and m['combined']==.625
    assert r['predictions_df'].loc[3,'rank_error']==1

def test_group_cv(data):
    r=ml.cross_validation(data,fit_function=ml.fit_pairwise_ranking,fit_kwargs={'features':['a','b'],'target':'accepted','group_column':'group'},task='ranking',group_column='group',folds=3)
    assert r['predictions_df'].groupby('group').fold.nunique().eq(1).all()
    assert len(r['predictions_df'])==len(data)

def test_search(data):
    kw={'features':['a','b'],'target':'y'}
    r=ml.select_features(data,fit_function=ml.fit_linear_regression,fit_kwargs=kw,metric='mae',direction='minimize',folds=3)
    assert len(r['trials_df'])==3 and r['best_params_df'].iloc[0].features==['a','b']
    s=ml.optimize_parameters(data,fit_function=ml.fit_decision_tree,fit_kwargs=kw,parameter_space={'max_depth':[1,3]},metric='mae',direction='minimize',folds=3)
    assert len(s['trials_df'])==2

def test_bootstrap_sensitivity_save(data,tmp_path):
    r=ml.bootstrap(data,metric_function=lambda d:d.y.mean(),group_column='group',n_trials=20)
    assert r.lower.iloc[0]<=r.upper.iloc[0]
    m=ml.fit_linear_regression(data,features=['a','b'],target='y')
    s=ml.sensitivity_analysis(data,model=m,feature='a',values=[0,1],metric_function=lambda d:d.score.mean())
    assert np.isclose(s.metric.diff().iloc[1],2)
    path=tmp_path/'model.joblib'
    ml.save_model(m,file_path=path)
    with pytest.raises(ValueError): ml.load_model(file_path=path)
    assert np.allclose(ml.load_model(file_path=path,trusted=True).score(data),m.score(data))

def test_invalid(data):
    with pytest.raises(ValueError): ml.fit_linear_regression(data,features=['y'],target='y')
    with pytest.raises(ValueError): ml.evaluate_ranking(data.assign(accepted=0,score=1),target='accepted',group_column='group')
