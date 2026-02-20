/**
 * Attendance Dashboard - Main Script
 * 
 * This handles loading and displaying attendance data
 * Features:
 * - Loads attendance records from backend
 * - Shows today's attendance by default
 * - Can filter by date
 * - Uses authenticated API calls (includes JWT token automatically)
 */

// This will be set by api.js when included
// const API_BASE and other utilities come from api.js

async function loadAttendance() {
  const dateInput = document.getElementById("dateInput");
  const selectedDate = dateInput.value || new Date().toISOString().slice(0, 10);

  try {
    // Fetch attendance and the small students count endpoint in parallel
    // Using apiCallJSON() automatically includes the token if user is logged in
    const [data, countJson] = await Promise.all([
      apiCallJSON('/attendance'),
      apiCallJSON('/students/count'),
    ]);

    // Handle errors
    if (!data || !countJson) {
      throw new Error('Failed to load data');
    }

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

