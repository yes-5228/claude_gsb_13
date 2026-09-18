import { useState } from 'react';

import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';

export default function InspectorCorrectionModal({ inspection, onClose, onSubmit, saving }) {
  const original = inspection?.corrections?.length
    ? inspection.corrections[0].original_inspector
    : inspection?.inspector ?? '';
  const [corrected, setCorrected] = useState(inspection?.inspector ?? '');
  const [reason, setReason] = useState('');
  const [operator, setOperator] = useState('');
  const [formError, setFormError] = useState(null);

  const submit = (event) => {
    event.preventDefault();
    const next = corrected.trim();
    const why = reason.trim();
    if (!next) {
      setFormError('请填写更正后的巡查人');
      return;
    }
    if (!why) {
      setFormError('请填写更正原因');
      return;
    }
    if (next === inspection.inspector) {
      setFormError('更正后的巡查人与当前巡查人相同，无需更正');
      return;
    }
    setFormError(null);
    onSubmit({ corrected_inspector: next, reason: why, operator: operator.trim() || null });
  };

  return (
    <Modal
      title="更正巡查人"
      onClose={onClose}
      width={560}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="inspector-correction" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : '确认更正'}
          </button>
        </>
      }
    >
      <div className="alert alert-info">
        更正只修改巡查人，<strong>巡查得分、等级与结论保持不变</strong>；原巡查人与更正原因会永久留存，可在详情中查询。
      </div>
      <form id="inspector-correction" className="form-grid" onSubmit={submit}>
        <Field label="当前巡查人">
          <input value={inspection.inspector} disabled readOnly />
        </Field>
        <Field label="原始巡查人">
          <input value={original} disabled readOnly />
        </Field>
        <Field label="更正后巡查人 *" full>
          <input
            value={corrected}
            onChange={(event) => setCorrected(event.target.value)}
            placeholder="请输入正确的巡查人姓名"
            autoFocus
          />
        </Field>
        <Field label="更正原因 *" full>
          <textarea
            rows="3"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="请说明巡查人填写错误的原因，如：替班代签 / 录入笔误"
          />
        </Field>
        <Field label="更正操作人" full hint="选填，默认记录为当前巡查人；用于审计是谁执行的更正">
          <input
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            placeholder="如：值班长"
          />
        </Field>
        {formError ? (
          <div className="alert alert-error" style={{ gridColumn: '1 / -1' }}>
            {formError}
          </div>
        ) : null}
      </form>
    </Modal>
  );
}
