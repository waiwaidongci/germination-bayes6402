import {request} from './client';import {Study} from '../types/domain';export const getStudies=()=>request<Study[]>('/studies');
