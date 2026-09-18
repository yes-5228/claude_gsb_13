import { useState } from 'react';

import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';

export default function InspectorCorrectionModal({ inspection, onClose, onSubmit, saving }) {
  const [inspector, setInspector] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState(null);

  const submit = (event) => {
    event.preventDefault();
    if (!inspector.trim()) {
      setError('请填写更正后的巡查人');
      return;
    }
    if (inspector.trim() === inspection.inspector) {
      setError('更正后的巡查人与当前巡查人一致');
      return;
    }
    if (!reason.trim()) {
      setError('请填写更正原因');
      return;
    }
    onSubmit({ inspector: inspector.trim(), reason: reason.trim() });
  };

  return (
    <Modal
      title="更正巡查人"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="inspector-correction" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中...' : '确认更正'}
          </button>
        </>
      }
    >
      <div className="alert alert-info">
        当前巡查人 <strong>{inspection.inspector}</strong>
        ，更正后原巡查人与更正原因将保留在更正记录中，巡查得分与结论不受影响。
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="inspector-correction" className="form-grid" onSubmit={submit}>
        <Field label="更正后巡查人 *">
          <input
            value={inspector}
            onChange={(event) => setInspector(event.target.value)}
            placeholder="请输入正确的巡查人姓名"
          />
        </Field>
        <Field label="更正原因 *" full>
          <textarea
            rows="3"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="如：录入时选错人员，实际巡查人为张三"
          />
        </Field>
      </form>
    </Modal>
  );
}
