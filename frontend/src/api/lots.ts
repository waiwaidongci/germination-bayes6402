import {request} from './client';import {Lot} from '../types/domain';export const getLots=(id:number)=>request<Lot[]>(`/studies/${id}/lots`);
