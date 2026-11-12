import numpy as np
from scipy.special import betaln,gammaln,logsumexp
from scipy.stats import beta as beta_distribution

def beta_binomial_pmf(m,a,b):
    if type(m) is not int or not 1<=m<=200:raise ValueError("未来试种数须为1–200整数")
    if isinstance(a,bool) or isinstance(b,bool) or not np.isfinite([a,b]).all() or min(a,b)<=0:raise ValueError("Beta形状须为有限正数")
    j=np.arange(m+1);logp=gammaln(m+1)-gammaln(j+1)-gammaln(m-j+1)+betaln(a+j,b+m-j)-betaln(a,b);normalizer=float(logsumexp(logp));mass=float(np.exp(normalizer))
    if not np.isfinite(mass) or abs(mass-1)>1e-7:raise ValueError("预测PMF归一偏差过大")
    p=np.exp(logp-normalizer);mu=a/(a+b)
    return {'pmf':[{'k':int(x),'probability':float(v)} for x,v in zip(j,p)],'mass_before_normalization':mass,'normalization_error':abs(mass-1),'mean':float(m*mu),'variance':float(m*mu*(1-mu)*(a+b+m)/(a+b+1)),'future_n':m}

def posterior_prediction(alpha,beta,n,k,threshold=.7,future_n=50):
    if type(n) is not int or type(k) is not int or not 1<=n<=100000 or not 0<=k<=n:raise ValueError("单批须为整数且1≤n、0≤k≤n")
    if isinstance(alpha,bool) or isinstance(beta,bool) or not np.isfinite([alpha,beta]).all() or min(alpha,beta)<=0:raise ValueError("先验形状须有限且为正")
    if type(threshold) not in (int,float) or not np.isfinite(threshold) or not 0<threshold<1:raise ValueError("研究阈值须为(0,1)有限比例")
    a=alpha+k;b=beta+n-k;interval=beta_distribution.ppf([.025,.975],a,b);x=np.linspace(0,1,201);cdf=beta_distribution.cdf(x,a,b);tail=float(beta_distribution.sf(threshold,a,b));prediction=beta_binomial_pmf(future_n,a,b)
    if not np.isfinite(interval).all() or not np.isfinite(cdf).all() or not np.isfinite(tail):raise ValueError("条件后验计算未能给出有限概率")
    return {'post_alpha':float(a),'post_beta':float(b),'raw_rate':k/n,'mean':float(a/(a+b)),'lower':float(interval[0]),'upper':float(interval[1]),'prob_gt_threshold':tail,'threshold':float(threshold),'data_weight':float(n/(n+alpha+beta)),'prior_weight':float((alpha+beta)/(n+alpha+beta)),'cdf':[{'p':float(v),'cdf':float(q)} for v,q in zip(x,cdf)],'prediction':prediction,'conditional_note':'95%等尾区间、阈值尾概率和同批未来计数预测均条件于点估αβ；不含超参数估计误差，不是种子合格保证或自动发货依据。'}
