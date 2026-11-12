from .eb_algorithm import fit_hyperparameters,validate_counts
from .posterior_algorithm import posterior_prediction
from ..utils.fingerprint import fingerprint
VERSION='bounded-multistart-betabinomial-eb-v1'
def prepare_snapshot(snapshot):
    lots=sorted(snapshot['lots'],key=lambda l:l['code']);counts=snapshot['counts']
    if len({x['id'] for x in lots})!=len(lots) or len({x['code'] for x in lots})!=len(lots):raise ValueError("批次身份或编号重复")
    by_lot={}
    for c in counts:
        if c['lot_id'] in by_lot:raise ValueError("每批只允许一条计数")
        by_lot[c['lot_id']]=c
    if set(by_lot)!=set(l['id'] for l in lots):raise ValueError("批次与计数必须一一对应，不能缺失或未知")
    ordered=[by_lot[l['id']] for l in lots];n=[c['n'] for c in ordered];k=[c['k'] for c in ordered];validate_counts(n,k)
    return lots,ordered,n,k

def analyze_germination(snapshot,threshold=.7,future_n=50):
    lots,counts,n,k=prepare_snapshot(snapshot);fit=fit_hyperparameters(n,k);rows=[]
    for lot,count in zip(lots,counts):rows.append({'lot':lot,'count':count,**posterior_prediction(fit['alpha'],fit['beta'],count['n'],count['k'],threshold,future_n)})
    canonical={'study':snapshot['study'],'lots':lots,'counts':counts}
    return {'algorithm_version':VERSION,'study':snapshot['study'],'fit':fit,'lots':rows,'threshold':float(threshold),'future_n':future_n,'input_snapshot':canonical,'fit_hash':fingerprint({'method':VERSION,'lots':[{'code':l['code'],'n':c['n'],'k':c['k']} for l,c in zip(lots,counts)],'bounds':[.01,5000.]}),'input_hash':fingerprint({'method':VERSION,'snapshot':canonical,'threshold':threshold,'future_n':future_n}),'assumptions':'独立批次、批内Binomial工作模型；不同批次潜在率以Beta近似。超参数由这些批次估计，全部后验/预测为条件EB，不包含超参数估计误差。','interpretation':'多起点只证明测试起点中的最佳合格收敛结果；贴边MLE标弱识别。阈值是研究问题，不是合格概率或自动发货指令。'}
