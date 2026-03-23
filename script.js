(function initReportBuilderPage() {
  const pool = document.getElementById('field-pool');
  const selected = document.getElementById('selected-fields');
  const previewBody = document.getElementById('preview-rows');

  if (!pool || !selected || !previewBody) return;

  const fields = ['Material', 'Plant', 'Order Qty', 'Open Qty', 'Delivery Date', 'Vendor'];

  fields.forEach((field) => {
    const chip = document.createElement('div');
    chip.className = 'chip';
    chip.textContent = field;
    chip.draggable = true;
    chip.addEventListener('dragstart', () => chip.classList.add('dragging'));
    chip.addEventListener('dragend', () => chip.classList.remove('dragging'));
    pool.appendChild(chip);
  });

  [pool, selected].forEach((zone) => {
    zone.addEventListener('dragover', (event) => event.preventDefault());
    zone.addEventListener('drop', () => {
      const dragging = document.querySelector('.dragging');
      if (dragging) zone.appendChild(dragging);
    });
  });

  const rows = Array.from({ length: 8 }, (_, i) => `
    <tr>
      <td>MAT-${1000 + i}</td>
      <td>Plant-${(i % 3) + 1}</td>
      <td>${120 + i * 5}</td>
      <td>${80 + i * 3}</td>
      <td>2026-03-${String(10 + i).padStart(2, '0')}</td>
    </tr>
  `).join('');
  previewBody.innerHTML = rows;
})();
