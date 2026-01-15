const API_BASE = "http://127.0.0.1:5000";

async function loadAttendance() {
  const dateInput = document.getElementById("dateInput");
  const selectedDate = dateInput.value || new Date().toISOString().slice(0, 10);

  try {
    // fetch attendance and the small students count endpoint in parallel
    const [attRes, countRes] = await Promise.all([
      fetch(`${API_BASE}/attendance`),
      fetch(`${API_BASE}/students/count`),
    ]);

    if (!attRes.ok) throw new Error('Attendance API error ' + attRes.status);
    if (!countRes.ok) throw new Error('Students count API error ' + countRes.status);

    const data = await attRes.json();
    const countJson = await countRes.json();

    const table = document.getElementById("attendanceTable");
    table.innerHTML = "";

    const todayRecords = data.filter(r => r.date === selectedDate);
    const presentIds = new Set(todayRecords.map(r => r.student_id));

    todayRecords.forEach(record => {
      const row = document.createElement("tr");

      row.innerHTML = `
        <td class="p-3">${record.student_id}</td>
        <td class="p-3">${record.date}</td>
        <td class="p-3">${record.time}</td>
        <td class="p-3 text-green-400 font-semibold">Present</td>
      `;

      table.appendChild(row);
    });

    // Stats
    document.getElementById("presentCount").innerText = presentIds.size;

    const TOTAL_STUDENTS = typeof countJson.count === 'number' ? countJson.count : 0;
    document.getElementById("totalStudents").innerText = TOTAL_STUDENTS;
    document.getElementById("absentCount").innerText =
      TOTAL_STUDENTS - presentIds.size;
  } catch (err) {
    console.error("Failed to load attendance or students:", err);
    // keep UI stable; show dashes on error
    document.getElementById("presentCount").innerText = "–";
    document.getElementById("totalStudents").innerText = "–";
    document.getElementById("absentCount").innerText = "–";
  }
}

// Auto load on page open
// basic loading state
document.getElementById("presentCount").innerText = "...";
document.getElementById("totalStudents").innerText = "...";
document.getElementById("absentCount").innerText = "...";

loadAttendance();

