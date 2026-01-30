const API = "http://127.0.0.1:5000";

async function loadStudents() {
  const res = await fetch(`${API}/students`);
  const students = await res.json();

  const table = document.getElementById("studentsTable");
  table.innerHTML = "";

  students.forEach(s => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="p-3">${s.student_id}</td>
      <td class="p-3">
        ${s.photo_path ? `<img src="../${s.photo_path}" class="h-12 rounded">` : "—"}
      </td>
    `;
    table.appendChild(row);
  });
}

loadStudents();

