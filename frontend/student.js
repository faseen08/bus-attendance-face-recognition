const API_BASE = "http://127.0.0.1:5000";

async function loadStudents() {
  try {
    // Changed ${API} to ${API_BASE}
    const res = await fetch(`${API_BASE}/students`);
    const students = await res.json();

    const table = document.getElementById("studentsTable");
    if (!table) return; // Safety check
    table.innerHTML = "";

    students.forEach(s => {
      const row = document.createElement("tr");
      row.className = "hover:bg-slate-700/50 transition-colors border-b border-slate-700";
      
      row.innerHTML = `
      <td class="p-3">
        <img src="${API_BASE}/${s.photo_path}" class="h-12 w-12 object-cover rounded-full border border-slate-600">
      </td>
      <td class="p-3">
        <div class="font-bold text-slate-200">${s.name || s.student_id}</div>
        <div class="text-xs text-slate-500">${s.student_id}</div>
      </td>
      <td class="p-3 text-slate-300 text-sm">
        ${s.bus_stop || 'Not Set'}
      </td>
      <td class="p-3 text-sm">
        ${s.on_leave === 1 
          ? '<span class="px-2 py-1 bg-amber-900/30 text-amber-400 rounded-full border border-amber-800/50">On Leave</span>'
          : '<span class="px-2 py-1 bg-green-900/30 text-green-400 rounded-full border border-green-800/50">Active</span>'
        }
      </td>
      `;
      table.appendChild(row);
    });
  } catch (err) {
    console.error("Failed to load students:", err);
  }
}

// Don't forget to call the function!
loadStudents();