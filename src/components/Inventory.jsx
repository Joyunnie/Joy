import { useState, useEffect } from 'react';

const STORAGE_KEY = 'catfood_inventory';

function loadInventory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; } catch { return []; }
}
function saveInventory(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export default function Inventory({ onUpdate }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState(loadInventory);
  const [name, setName] = useState('');
  const [amount, setAmount] = useState('');
  const [editIdx, setEditIdx] = useState(null);

  const save = (updated) => {
    saveInventory(updated);
    setItems(updated);
    if (onUpdate) onUpdate();
  };

  const handleAdd = () => {
    const n = name.trim();
    if (!n || !amount) return;
    if (editIdx != null) {
      const updated = [...items];
      updated[editIdx] = { name: n, amount: Number(amount) };
      save(updated);
      setEditIdx(null);
    } else {
      save([...items, { name: n, amount: Number(amount) }]);
    }
    setName(''); setAmount('');
  };

  const handleEdit = (i) => {
    setName(items[i].name);
    setAmount(items[i].amount);
    setEditIdx(i);
  };

  const handleDelete = (i) => {
    save(items.filter((_, idx) => idx !== i));
    if (editIdx === i) { setEditIdx(null); setName(''); setAmount(''); }
  };

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">재고 관리</span>
        {items.length > 0 && <span className="text-[9px] text-gray-400">({items.length})</span>}
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          <div className="flex gap-1">
            <input type="text"
              className="flex-1 text-[10px] border border-gray-300 rounded px-1 py-0.5"
              placeholder="재료명" value={name} onChange={(e) => setName(e.target.value)} />
            <input type="number"
              className="w-16 text-[10px] border border-gray-300 rounded px-0.5 py-0.5 text-right"
              placeholder="g" value={amount} onChange={(e) => setAmount(e.target.value)} min={0} step="any" />
            <button onClick={handleAdd}
              className="text-[9px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 whitespace-nowrap">
              {editIdx != null ? '수정' : '추가'}
            </button>
            {editIdx != null && (
              <button onClick={() => { setEditIdx(null); setName(''); setAmount(''); }}
                className="text-[9px] px-1 py-0.5 bg-gray-300 rounded hover:bg-gray-400">취소</button>
            )}
          </div>
          {items.length > 0 && (
            <div className="max-h-32 overflow-y-auto border rounded">
              {items.map((item, i) => (
                <div key={i} className="flex items-center gap-1 px-1 py-0.5 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                  <span className="flex-1 text-[10px] truncate">{item.name}</span>
                  <span className="text-[10px] text-gray-600 font-mono shrink-0">{item.amount}g</span>
                  <button onClick={() => handleEdit(i)} className="text-[9px] text-blue-400 hover:text-blue-600 px-0.5">편집</button>
                  <button onClick={() => handleDelete(i)} className="text-[9px] text-red-400 hover:text-red-600 px-0.5">삭제</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
