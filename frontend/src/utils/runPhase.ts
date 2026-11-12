import {Run} from '../types/domain';
export const runPhaseTitle=(run:Run)=>run.phase==='failed'?'拟合未完成':run.phase==='recovering'?'中断后自动重算':run.phase==='waiting'?'排队等待独立worker':'独立worker正在多起点拟合与条件预测';
export const runPhaseNote=(run:Run)=>run.phase==='failed'?'该次计算已失败；重提同配置可重新研究，历史结果不受影响。':run.phase==='recovering'?'计算曾中断，系统已按原计数快照重新排队；半份结果不会用于审阅或下载。':run.phase==='waiting'?'任务已持久排队；worker接手后按提交时的计数快照计算。':'本页每2秒刷新；不以阈值/未来m选择先验。';
