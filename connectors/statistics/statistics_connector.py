"""Local DataFrame statistical analysis. Inputs are never mutated."""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


def _frame(data, columns, groups=()):
    if not isinstance(data, pd.DataFrame) or not data.columns.is_unique:
        raise ValueError('重複のない列名を持つDataFrameを指定してください。')
    columns = list(columns)
    if not columns or len(set(columns)) != len(columns):
        raise ValueError('分析対象列を重複なく指定してください。')
    if set(columns) & set(groups):
        raise ValueError('分析対象列とグループ列を分けてください。')
    frame = data.loc[:, list(groups) + columns].copy()
    for c in columns:
        frame[c] = pd.to_numeric(frame[c], errors='raise').astype(float)
        if np.isinf(frame[c]).any():
            raise ValueError('無限大は使用できません。')
    return frame


def _groups(frame, group_columns):
    if not group_columns:
        yield {}, frame
    else:
        keys = list(group_columns)
        for key, part in frame.groupby(keys[0] if len(keys) == 1 else keys,
                                       dropna=False, observed=True, sort=False):
            yield dict(zip(keys, (key,) if len(keys) == 1 else key)), part


def describe(data, *, columns, group_columns=()):
    rows = []
    for key, part in _groups(_frame(data, columns, group_columns), group_columns):
        for c in columns:
            s = part[c]
            rows.append(dict(key, column=c, count=int(s.count()), missing=int(s.isna().sum()),
                             missing_rate=s.isna().mean(), mean=s.mean(), std=s.std(),
                             min=s.min(), q25=s.quantile(.25), median=s.median(),
                             q75=s.quantile(.75), max=s.max()))
    return pd.DataFrame(rows)


def distribution(data, *, columns, bins=10, group_columns=()):
    if not isinstance(bins, int) or bins < 1:
        raise ValueError('binsは正の整数です。')
    rows = []
    for key, part in _groups(_frame(data, columns, group_columns), group_columns):
        for c in columns:
            s = part[c].dropna()
            if s.empty:
                continue
            counts, edges = np.histogram(s, bins=bins)
            for i, n in enumerate(counts):
                rows.append(dict(key, column=c, lower=edges[i], upper=edges[i+1], count=int(n),
                                 proportion=n/len(s), skew=s.skew(), kurtosis=s.kurt()))
    return pd.DataFrame(rows)


def correlation(data, *, columns, method='pearson', group_columns=()):
    methods = {'pearson': stats.pearsonr, 'spearman': stats.spearmanr, 'kendall': stats.kendalltau}
    if method not in methods:
        raise ValueError('未対応の相関係数です。')
    rows = []
    for key, part in _groups(_frame(data, columns, group_columns), group_columns):
        for a, b in combinations(columns, 2):
            pair = part[[a,b]].dropna()
            r, p = (methods[method](pair[a], pair[b]) if len(pair) >= 2 and
                    pair[a].nunique() > 1 and pair[b].nunique() > 1 else (np.nan,np.nan))
            rows.append(dict(key, column_a=a, column_b=b, method=method, n=len(pair), correlation=r, p_value=p))
    return pd.DataFrame(rows)


def multicollinearity(data, *, columns, group_columns=()):
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    rows = []
    for key, part in _groups(_frame(data, columns, group_columns), group_columns):
        x = part[list(columns)].dropna().to_numpy()
        if len(x) <= len(columns):
            raise ValueError('VIF算出に必要な完全データが不足しています。')
        design = np.column_stack([np.ones(len(x)), x])
        for i,c in enumerate(columns,1):
            vif = (np.nan if np.ptp(x[:,i-1]) == 0 else
                   float(variance_inflation_factor(design,i)))
            rows.append(dict(key, column=c, n=len(x), vif=vif))
    return pd.DataFrame(rows)


def compare_groups(data, *, columns, group_columns):
    if not group_columns:
        raise ValueError('グループ列を指定してください。')
    return describe(data, columns=columns, group_columns=group_columns)


def _samples(data, column, group_column, group_a, group_b):
    if group_a == group_b:
        raise ValueError('異なるグループを指定してください。')
    f = _frame(data, [column], [group_column])
    a = f.loc[f[group_column].eq(group_a),column].dropna().to_numpy()
    b = f.loc[f[group_column].eq(group_b),column].dropna().to_numpy()
    if min(len(a),len(b)) < 2:
        raise ValueError('各グループに2件以上必要です。')
    return a,b


def hypothesis_test(data, *, column, group_column, group_a, group_b, method='welch', alternative='two-sided'):
    a,b = _samples(data,column,group_column,group_a,group_b)
    if method in ('welch','student'):
        result = stats.ttest_ind(a,b,equal_var=method=='student',alternative=alternative)
    elif method == 'mannwhitney':
        result = stats.mannwhitneyu(a,b,alternative=alternative)
    else:
        raise ValueError('未対応の検定です。')
    return pd.DataFrame([dict(column=column,group_a=group_a,group_b=group_b,method=method,
                              n_a=len(a),n_b=len(b),statistic=result.statistic,p_value=result.pvalue)])


def effect_size(data, *, column, group_column, group_a, group_b, method='cohen_d'):
    a,b = _samples(data,column,group_column,group_a,group_b)
    if method in ('cohen_d','hedges_g'):
        pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
        value = (a.mean()-b.mean())/pooled if pooled else np.nan
        if method == 'hedges_g':
            value *= 1-3/(4*(len(a)+len(b))-9)
    elif method == 'rank_biserial':
        value = 2*stats.mannwhitneyu(a,b).statistic/(len(a)*len(b))-1
    else:
        raise ValueError('未対応の効果量です。')
    return pd.DataFrame([dict(column=column,group_a=group_a,group_b=group_b,method=method,effect_size=value)])
