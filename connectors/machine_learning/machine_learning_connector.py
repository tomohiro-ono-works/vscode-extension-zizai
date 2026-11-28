"""Local supervised learning, ranking, validation and parameter search."""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import GroupKFold, KFold, ParameterGrid, ParameterSampler, StratifiedKFold
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class Model:
    """Keep training-only preprocessing with the fitted estimator."""
    def __init__(self, estimator, features, categories=(), interactions=False, scale=False, task='regression'):
        self.estimator = estimator
        self.features = list(features)
        self.categories = list(categories)
        self.interactions = interactions
        self.scale = scale
        self.task = task
        if not self.features or len(set(self.features+self.categories)) != len(self.features+self.categories):
            raise ValueError('説明変数を重複なく指定してください。')

    def transform(self, data, fit=False):
        if not isinstance(data,pd.DataFrame) or not data.columns.is_unique:
            raise ValueError('列名の一意なDataFrameが必要です。')
        x = data[self.features].to_numpy(dtype=float)
        if not np.isfinite(x).all():
            raise ValueError('数値列の欠損・無限大は前処理してください。')
        if self.scale:
            if fit:
                self.scaler = StandardScaler().fit(x)
            x = self.scaler.transform(x)
        names = self.features.copy()
        arrays = [x]
        if self.categories:
            c = data[self.categories].astype('string').fillna('__MISSING__').astype(str)
            if fit:
                self.encoder = OneHotEncoder(handle_unknown='ignore',drop='first').fit(c)
            z = self.encoder.transform(c).toarray()
            zn = list(self.encoder.get_feature_names_out(self.categories))
            arrays.append(z)
            names.extend(zn)
            if self.interactions:
                arrays.append((x[:,:,None]*z[:,None,:]).reshape(len(x),-1))
                names.extend(f'{a} × {b}' for a in self.features for b in zn)
        if fit:
            self.feature_names = names
        return np.column_stack(arrays)

    def score(self,data):
        x = self.transform(data)
        if self.task == 'classification':
            return self.estimator.predict_proba(x)[:,list(self.estimator.classes_).index(1)]
        if self.task == 'pairwise':
            return self.estimator.decision_function(x)
        return self.estimator.predict(x)


def _target(data,target,features,categories,task):
    if target in list(features)+list(categories):
        raise ValueError('目的変数を説明変数に含めないでください。')
    y = data[target].to_numpy(dtype=float)
    if not len(y) or not np.isfinite(y).all():
        raise ValueError('目的変数は欠損のない数値が必要です。')
    if task in ('classification','pairwise') and set(y) != {0,1}:
        raise ValueError('二値分類は0と1の両方が必要です。')
    return y


def _fit(data, *, estimator, features, target, categories=(), interactions=False, scale=False, task='regression'):
    y = _target(data,target,features,categories,task)
    m = Model(estimator,features,categories,interactions,scale,task)
    m.estimator.fit(m.transform(data,fit=True),y)
    return m


def fit_linear_regression(data, *, features, target, categories=(), interactions=False, scale=False, params=None):
    return _fit(data,estimator=LinearRegression(**(params or {})),features=features,target=target,categories=categories,interactions=interactions,scale=scale)


def fit_logistic_regression(data, *, features, target, categories=(), interactions=False, scale=False, params=None):
    return _fit(data,estimator=LogisticRegression(**{'max_iter':1000,**(params or {})}),features=features,target=target,categories=categories,interactions=interactions,scale=scale,task='classification')


def _tree(data, *, features,target, categories, interactions,scale,task,params,forest):
    types = {'regression': RandomForestRegressor if forest else DecisionTreeRegressor,
             'classification': RandomForestClassifier if forest else DecisionTreeClassifier}
    if task not in types:
        raise ValueError('taskはregressionまたはclassificationです。')
    return _fit(data,estimator=types[task](**{'random_state':42,**(params or {})}),features=features,target=target,categories=categories,interactions=interactions,scale=scale,task=task)


def fit_decision_tree(data, *, features,target,categories=(),interactions=False,scale=False,task='regression',params=None):
    return _tree(data,features=features,target=target,categories=categories,interactions=interactions,scale=scale,task=task,params=params,forest=False)


def fit_random_forest(data, *, features,target,categories=(),interactions=False,scale=False,task='regression',params=None):
    return _tree(data,features=features,target=target,categories=categories,interactions=interactions,scale=scale,task=task,params=params,forest=True)


def _group_indices(data, group_column):
    if not group_column or data[group_column].isna().any():
        raise ValueError('欠損のないグループ列が必要です。')
    return list(data.groupby(group_column,sort=False,observed=True).indices.values())


def fit_pairwise_ranking(data, *, features,target,group_column,categories=(),interactions=False,scale=False,params=None):
    if group_column in list(features)+list(categories) or group_column == target:
        raise ValueError('グループ列は説明変数・目的変数と分離してください。')
    y = _target(data,target,features,categories,'pairwise')
    m = Model(LogisticRegression(**{'max_iter':1000,**(params or {}),'fit_intercept':False}),features,categories,interactions,scale,'pairwise')
    x = m.transform(data,fit=True)
    diffs = []
    for idx in _group_indices(data,group_column):
        for a in idx[y[idx]==1]:
            for b in idx[y[idx]==0]:
                diffs.append(x[a]-x[b])
    if not diffs:
        raise ValueError('採用・不採用の組を持つグループが必要です。')
    d = np.asarray(diffs)
    m.estimator.fit(np.vstack([d,-d]),np.r_[np.ones(len(d)),np.zeros(len(d))])
    return m


def fit_lambdamart(data, *, features,target,group_column,categories=(),interactions=False,scale=False,params=None):
    from lightgbm import LGBMRanker
    if group_column in list(features)+list(categories) or group_column == target:
        raise ValueError('グループ列は説明変数・目的変数と分離してください。')
    y = _target(data,target,features,categories,'pairwise')
    groups = _group_indices(data,group_column)
    if not any(len(set(y[g]))>1 for g in groups):
        raise ValueError('採用・不採用の組が必要です。')
    m = Model(LGBMRanker(**{'objective':'lambdarank','verbosity':-1,'random_state':42,'n_jobs':1,**(params or {})}),features,categories,interactions,scale,'ranking')
    x = m.transform(data,fit=True)
    order = np.concatenate(groups)
    m.estimator.fit(x[order],y[order].astype(int),group=[len(g) for g in groups])
    return m


def predict(data, *, model, score_column='score', group_column=None, rank_column='rank', threshold=.5):
    if score_column in data or (group_column and (rank_column in data or rank_column==score_column)):
        raise ValueError('出力列名が既存列と重複しています。')
    result = data.copy()
    result[score_column] = model.score(data)
    if group_column:
        _group_indices(data,group_column)
        result[rank_column] = result.groupby(group_column,sort=False,observed=True)[score_column].rank(method='first',ascending=False).astype(int)
    if model.task=='classification':
        if 'prediction' in result:
            raise ValueError('prediction列が重複しています。')
        result['prediction'] = (result[score_column]>=threshold).astype(int)
    return result


def inspect_model(model):
    e = model.estimator
    if hasattr(e,'coef_'):
        return pd.DataFrame({'feature':model.feature_names,'coefficient':np.asarray(e.coef_).reshape(-1)})
    if hasattr(e,'feature_importances_'):
        return pd.DataFrame({'feature':model.feature_names,'importance':e.feature_importances_})
    raise ValueError('係数・重要度を取得できません。')


def _metric_frame(values, custom_metrics=None, data=None):
    values = dict(values)
    for name, fn in (custom_metrics or {}).items():
        if name in values or not callable(fn):
            raise ValueError('カスタム指標名の重複または関数の指定エラーです。')
        values[name] = float(fn(data.copy(),values.copy()))
    return pd.DataFrame({'metric':list(values),'value':list(values.values())})


def evaluate_regression(data, *, target, score_column='score', custom_metrics=None, n_features=None):
    y,p = data[target],data[score_column]
    r2 = metrics.r2_score(y,p) if len(y)>1 else np.nan
    values = {'r2':r2,'rmse':np.sqrt(metrics.mean_squared_error(y,p)),'mae':metrics.mean_absolute_error(y,p),
              'mape':metrics.mean_absolute_percentage_error(y,p) if (y!=0).all() else np.nan}
    if n_features is not None:
        values['adjusted_r2'] = 1-(1-r2)*(len(y)-1)/(len(y)-n_features-1) if len(y)>n_features+1 else np.nan
    return _metric_frame(values,custom_metrics,data)


def evaluate_classification(data, *, target,score_column='score',threshold=.5,custom_metrics=None):
    y,p = data[target].to_numpy(),data[score_column].to_numpy(dtype=float)
    if not set(y)<= {0,1} or not np.isfinite(p).all() or (p<0).any() or (p>1).any():
        raise ValueError('正解は0/1、予測値は0〜1の確率です。')
    pred = p>=threshold
    values = {'accuracy':metrics.accuracy_score(y,pred),'precision':metrics.precision_score(y,pred,zero_division=0),
              'recall':metrics.recall_score(y,pred,zero_division=0),'f1':metrics.f1_score(y,pred,zero_division=0),
              'auc':metrics.roc_auc_score(y,p) if len(set(y))==2 else np.nan,'log_loss':metrics.log_loss(y,p,labels=[0,1])}
    return _metric_frame(values,custom_metrics,data)


def evaluate_ranking(data, *, target,group_column,score_column='score',k=5,custom_metrics=None):
    if not isinstance(k,int) or k<1:
        raise ValueError('kは正の整数です。')
    if not set(data[target])<= {0,1} or not np.isfinite(data[score_column].to_numpy(dtype=float)).all():
        raise ValueError('正解は0/1、スコアは有限数です。')
    if {'rank','rank_error'} & set(data.columns):
        # Recompute rather than trusting previously assigned ranks.
        detail = data.drop(columns=['rank','rank_error'],errors='ignore').copy()
    else:
        detail = data.copy()
    groups = _group_indices(detail,group_column)
    if not groups:
        raise ValueError('評価対象がありません。')
    detail['rank'] = detail.groupby(group_column,sort=False,observed=True)[score_column].rank(method='first',ascending=False).astype(int)
    detail['rank_error'] = (detail['rank']-1).where(detail[target].eq(1))
    rows = []
    for idx in groups:
        g = detail.iloc[idx].sort_values('rank')
        y = g[target].to_numpy()
        ranks = np.flatnonzero(y==1)+1
        if not len(ranks):
            raise ValueError('正解候補がないグループは評価対象から事前に除外してください。')
        dcg = np.sum(y[:k]/np.log2(np.arange(2,min(k,len(y))+2)))
        ideal = np.sum(1/np.log2(np.arange(2,min(k,len(ranks))+2)))
        pos,neg = g.loc[g[target]==1,score_column].to_numpy(),g.loc[g[target]==0,score_column].to_numpy()
        delta = pos[:,None]-neg[None,:]
        rows.append({group_column:g[group_column].iloc[0],'hit@1':float(ranks[0]==1),f'hit@{k}':float(ranks[0]<=k),
                     'mrr':1/ranks[0],f'ndcg@{k}':dcg/ideal,'mean_rank':ranks.mean(),'mean_rank_error':(ranks-1).mean(),
                     'pairwise_accuracy':((delta>0)+.5*(delta==0)).mean() if delta.size else np.nan})
    by_group = pd.DataFrame(rows)
    values = by_group.drop(columns=group_column).mean().to_dict()
    return {'metrics_df':_metric_frame(values,custom_metrics,detail),'predictions_df':detail,'groups_df':by_group}


def _splits(data,target,group_column,folds,classification=False,random_state=42):
    if group_column:
        _group_indices(data,group_column)
        return GroupKFold(n_splits=folds).split(data,groups=data[group_column])
    if classification:
        return StratifiedKFold(n_splits=folds,shuffle=True,random_state=random_state).split(data,data[target])
    return KFold(n_splits=folds,shuffle=True,random_state=random_state).split(data)


def _evaluate(data,task,target,group_column,k,custom_metrics):
    if task=='ranking':
        return evaluate_ranking(data,target=target,group_column=group_column,k=k,custom_metrics=custom_metrics)['metrics_df']
    fn = evaluate_classification if task=='classification' else evaluate_regression
    return fn(data,target=target,custom_metrics=custom_metrics)


def cross_validation(data, *, fit_function, fit_kwargs, task='regression', group_column=None, folds=5, k=5, custom_metrics=None, random_state=42):
    target = fit_kwargs['target']
    if task not in ('regression','classification','ranking') or (task=='ranking' and not group_column):
        raise ValueError('taskまたはグループ列が不正です。')
    if fit_kwargs.get('group_column',group_column)!=group_column:
        raise ValueError('学習と検証のグループ列を一致させてください。')
    rows, predictions = [],[]
    for i,(train,test) in enumerate(_splits(data,target,group_column,folds,task=='classification',random_state),1):
        model = fit_function(data.iloc[train],**fit_kwargs)
        p = predict(data.iloc[test],model=model,group_column=group_column if task=='ranking' else None)
        if task=='ranking':
            p = evaluate_ranking(p,target=target,group_column=group_column,k=k)['predictions_df']
        m = _evaluate(p,task,target,group_column,k,custom_metrics)
        rows.append(m.assign(fold=i)); predictions.append(p.assign(fold=i))
    validation = pd.concat(rows,ignore_index=True)
    return {'validation_df':validation,'metrics_df':validation.groupby('metric',sort=False).value.agg(['mean','std']).reset_index(),
            'predictions_df':pd.concat(predictions,ignore_index=True)}


def optimize_parameters(data, *, fit_function, fit_kwargs, parameter_space, metric, direction='maximize', search='grid', n_trials=30, task='regression',group_column=None,folds=5,k=5,custom_metrics=None,random_state=42):
    if direction not in ('maximize','minimize') or search not in ('grid','random'):
        raise ValueError('探索方式または方向が不正です。')
    candidates = ParameterGrid(parameter_space) if search=='grid' else ParameterSampler(parameter_space,n_iter=n_trials,random_state=random_state)
    return _search(data,fit_function,fit_kwargs,({'params':{**fit_kwargs.get('params',{}),**p}} for p in candidates),metric,direction,task,group_column,folds,k,custom_metrics,random_state)


def select_features(data, *, fit_function,fit_kwargs,metric,direction='maximize',task='regression',group_column=None,folds=5,k=5,custom_metrics=None,random_state=42):
    fs = fit_kwargs['features']
    candidates = ({'features':list(c)} for n in range(1,len(fs)+1) for c in combinations(fs,n))
    return _search(data,fit_function,fit_kwargs,candidates,metric,direction,task,group_column,folds,k,custom_metrics,random_state)


def _search(data,fit_function,fit_kwargs,candidates,metric,direction,task,group_column,folds,k,custom_metrics,random_state):
    if direction not in ('maximize','minimize'):
        raise ValueError('方向が不正です。')
    rows, best, best_result = [],None,None
    for i,change in enumerate(candidates,1):
        kwargs = {**fit_kwargs,**change}
        result = cross_validation(data,fit_function=fit_function,fit_kwargs=kwargs,task=task,group_column=group_column,folds=folds,k=k,custom_metrics=custom_metrics,random_state=random_state)
        values = result['metrics_df'].set_index('metric')['mean'].to_dict()
        value = values[metric]
        rows.append({'trial':i,**change,**values})
        if np.isfinite(value) and (best is None or (value>best[0] if direction=='maximize' else value<best[0])):
            best = (value,kwargs,change,i); best_result = result
    if best is None:
        raise ValueError('有効な探索結果がありません。')
    return {'model':fit_function(data,**best[1]),'best_params_df':pd.DataFrame([{'trial':best[3],**best[2],metric:best[0]}]),
            'trials_df':pd.DataFrame(rows),**best_result}


def compare_models(results):
    return pd.concat([frame.assign(model=name) for name,frame in results.items()],ignore_index=True)


def bootstrap(data, *, metric_function, group_column=None,n_trials=1000,confidence=.95,random_state=42):
    if not len(data) or n_trials<2 or not 0<confidence<1:
        raise ValueError('ブートストラップの指定が不正です。')
    rng = np.random.default_rng(random_state)
    units = _group_indices(data,group_column) if group_column else [np.array([i]) for i in range(len(data))]
    values = []
    for _ in range(n_trials):
        parts = []
        for j,i in enumerate(rng.integers(len(units),size=len(units))):
            p = data.iloc[units[i]].copy()
            if group_column:
                p[group_column] = j
            parts.append(p)
        values.append(float(metric_function(pd.concat(parts,ignore_index=True))))
    alpha = (1-confidence)/2
    return pd.DataFrame([{'estimate':float(metric_function(data.copy())),'lower':np.quantile(values,alpha),'upper':np.quantile(values,1-alpha),'confidence':confidence,'n_trials':n_trials}])


def sensitivity_analysis(data, *, model,feature,values,metric_function):
    if feature not in model.features:
        raise ValueError('数値説明変数を指定してください。')
    rows=[]
    for v in values:
        d=data.copy(); d[feature]=v
        rows.append({'feature':feature,'value':v,'metric':float(metric_function(predict(d,model=model)))})
    return pd.DataFrame(rows)


def save_model(model, *, file_path):
    import joblib
    path=Path(file_path)
    if path.exists():
        raise FileExistsError(path)
    joblib.dump(model,path)
    return path


def load_model(*, file_path, trusted=False):
    import joblib
    if not trusted:
        raise ValueError('信頼できるモデルファイルのみtrusted=Trueで読み込んでください。')
    model=joblib.load(file_path)
    if not isinstance(model,Model):
        raise ValueError('未対応のモデルです。')
    return model
