"""Bounded multistart Beta-Binomial marginal MLE in log-shape coordinates."""
import math
import numpy as np
from scipy.special import betaln,digamma,gammaln
from scipy.optimize import minimize
SHAPE_BOUNDS=(.01,5000.)
LOG_BOUNDS=np.log(SHAPE_BOUNDS)
PROJECTED_GRAD_TOL=1e-4

def validate_counts(n,k,require_study=True):
    N=np.asarray(n,dtype=object);K=np.asarray(k,dtype=object)
    if N.ndim!=1 or K.ndim!=1 or len(N)!=len(K) or len(N)<1:raise ValueError("n/k须为同长非空向量")
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,np.integer)) for v in list(N)+list(K)):raise ValueError("n/k必须为整数计数，不接受布尔或小数")
    try:N=np.asarray(N,dtype=np.int64);K=np.asarray(K,dtype=np.int64)
    except (OverflowError,ValueError):raise ValueError("计数超出整数范围")
    if np.any((N<1)|(N>100000)|(K<0)|(K>N)):raise ValueError("须满足1≤n≤100000、0≤k≤n")
    if require_study:
        if not 8<=len(N)<=200:raise ValueError("拟合要求8–200个独立批次")
        if np.sum(K)==0 or np.sum(K)==np.sum(N):raise ValueError("全部0或全部1无法稳定估计先验，拒绝拟合")
    return N,K

def loglik_and_gradient(theta,n,k):
    N,K=validate_counts(n,k,False)
    try:theta=np.asarray(theta,dtype=float)
    except (ValueError,TypeError,OverflowError):raise ValueError("log形状参数须为有限数值")
    if theta.shape!=(2,) or not np.isfinite(theta).all():raise ValueError("log形状参数须为两个有限值")
    a,b=np.exp(theta)
    if not np.isfinite(a+b) or min(a,b)<=0:raise ValueError("形状参数须有限且为正")
    common=digamma(a+b)-digamma(N+a+b)
    ll=np.sum(gammaln(N+1)-gammaln(K+1)-gammaln(N-K+1)+betaln(K+a,N-K+b)-betaln(a,b))
    grad=np.array([a*np.sum(digamma(K+a)-digamma(a)+common),b*np.sum(digamma(N-K+b)-digamma(b)+common)])
    return float(ll),grad

def objective(theta,n,k):
    value,grad=loglik_and_gradient(theta,n,k);return -value,-grad

def projected_gradient(theta,gradient):
    x=np.asarray(theta);g=np.asarray(gradient,dtype=float).copy();lb,ub=LOG_BOUNDS
    g[(x<=lb+1e-7)&(g>0)]=0.;g[(x>=ub-1e-7)&(g<0)]=0.
    return g

def fit_hyperparameters(n,k):
    N,K=validate_counts(n,k);pooled=(float(np.sum(K))+.5)/(float(np.sum(N))+1)
    starts=[(1.,1.),(2.,2.),(8.,4.),(.2,.2),(1.,8.),(8.,1.)]+[(pooled*s,(1-pooled)*s) for s in (2.,20.,200.,5000.)]
    starts=list(dict.fromkeys(tuple(float(v) for v in np.clip(pair,*SHAPE_BOUNDS)) for pair in starts));attempts=[]
    for index,pair in enumerate(starts):
        start=np.log(pair);initial,_=objective(start,N,K)
        result=minimize(objective,start,args=(N,K),jac=True,method='L-BFGS-B',bounds=[tuple(LOG_BOUNDS)]*2,options={'maxiter':2000,'maxls':50,'gtol':1e-8,'ftol':1e-13})
        value,gradient=objective(result.x,N,K);pg=projected_gradient(result.x,gradient);pg_norm=float(np.max(np.abs(pg)));a,b=np.clip(np.exp(result.x),*SHAPE_BOUNDS)
        accepted=bool(result.success and np.isfinite(value) and np.isfinite(gradient).all() and pg_norm<=PROJECTED_GRAD_TOL)
        attempts.append({'index':index,'start_alpha':pair[0],'start_beta':pair[1],'initial_loglik':-float(initial),'alpha':float(a),'beta':float(b),'loglik':-float(value),'optimizer_success':bool(result.success),'accepted':accepted,'status':int(result.status),'message':str(result.message),'iterations':int(result.nit),'evaluations':int(result.nfev),'log_gradient':gradient.tolist(),'projected_gradient':pg.tolist(),'projected_gradient_norm':pg_norm,'log_parameters':result.x.tolist()})
    candidates=[x for x in attempts if x['accepted']]
    if not candidates:raise ValueError("所有起点未达到收敛与投影梯度要求，拒绝输出先验")
    best=max(candidates,key=lambda x:x['loglik']);a,b=best['alpha'],best['beta'];boundary=[]
    for name,value in [('alpha',a),('beta',b)]:
        if abs(math.log(value)-LOG_BOUNDS[0])<=1e-5:boundary.append(name+':lower')
        if abs(math.log(value)-LOG_BOUNDS[1])<=1e-5:boundary.append(name+':upper')
    failed=[x['loglik'] for x in attempts if not x['accepted'] and np.isfinite(x['loglik'])];failed_better=bool(failed and max(failed)>best['loglik']+1e-6)
    return {'alpha':a,'beta':b,'mean':a/(a+b),'precision':a+b,'loglik':best['loglik'],'selected_start':best['index'],'attempts':attempts,'accepted_starts':len(candidates),'total_starts':len(attempts),'boundary_parameters':boundary,'weak_identification':bool(boundary or failed_better),'failed_better_objective':failed_better,'projected_gradient_norm':best['projected_gradient_norm'],'log_gradient':best['log_gradient'],'projected_gradient':best['projected_gradient'],'shape_bounds':list(SHAPE_BOUNDS),'gradient_tolerance':PROJECTED_GRAD_TOL,'gradient_kind':'negative_loglik_wrt_log_shapes','fit_note':'在测试的起点中选择通过收敛与投影梯度检查的最大边际似然；不声称全局最优。贴边标弱识别，后验不包含超参数估计误差。'}
