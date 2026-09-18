import { http } from './client.js';

const RESOURCE = '/inspections';

export const inspectionApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  // 更正巡查人：需填写更正后的巡查人与更正原因，评分与结论不变
  correctInspector: (id, payload) =>
    http.post(`${RESOURCE}/${id}/inspector-correction`, payload),
};
