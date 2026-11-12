import {RunPhase} from '../../constants/enums';
export function StatusBadge({status,phase,recovered}:{status:string;phase?:keyof typeof RunPhase;recovered?:boolean}){
  const key=phase||(status as keyof typeof RunPhase);
  const label=RunPhase[key]||status;
  return <span className={'status '+key}><i/>{label}{key==='recovering'&&recovered?' · 已自动接手':''}</span>;
}
