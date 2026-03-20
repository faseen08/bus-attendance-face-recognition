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

async function loadRequests() {
  const userTable = document.getElementById("userRequestsTable");
  const leaveTable = document.getElementById("leaveRequestsTable");
  if (!userTable || !leaveTable) return;

  userTable.innerHTML = "";
  leaveTable.innerHTML = "";

  try {
    const requests = await apiCallJSON('/admin/requests?status=PENDING');
    if (!requests) throw new Error("Failed to load requests");

    const userReqs = requests.filter(r => r.request_type === 'STUDENT_ADD' || r.request_type === 'DRIVER_ADD');
    const leaveReqs = requests.filter(r => r.request_type === 'LEAVE');

    userReqs.forEach(r => {
      const payload = JSON.parse(r.payload || "{}");
      const row = document.createElement("tr");
      const detail = r.request_type === 'STUDENT_ADD'
        ? `${payload.name || payload.student_id} | Bus ${payload.bus_number || '-'}`
        : `${payload.name || payload.driver_id} | Bus ${payload.bus_number || '-'}`;
      row.innerHTML = `
        <td class="p-3">${r.request_type === 'STUDENT_ADD' ? 'Student' : 'Driver'}</td>
        <td class="p-3">${r.requester_id}</td>
        <td class="p-3 text-slate-300 text-sm">${detail}</td>
        <td class="p-3">
          <button class="approve-req bg-green-600 hover:bg-green-500 px-3 py-1 rounded text-sm mr-2" data-id="${r.id}">Approve</button>
          <button class="reject-req bg-red-600 hover:bg-red-500 px-3 py-1 rounded text-sm" data-id="${r.id}">Reject</button>
        </td>
      `;
      userTable.appendChild(row);
    });

    leaveReqs.forEach(r => {
      const payload = JSON.parse(r.payload || "{}");
      const desired = (payload.desired_status ?? 1) === 1 ? "Leave" : "Active";
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="p-3">${payload.student_id || r.requester_id}</td>
        <td class="p-3">${desired}</td>
        <td class="p-3 text-slate-300 text-sm">${payload.reason || '-'}</td>
        <td class="p-3">
          <button class="approve-req bg-green-600 hover:bg-green-500 px-3 py-1 rounded text-sm mr-2" data-id="${r.id}">Approve</button>
          <button class="reject-req bg-red-600 hover:bg-red-500 px-3 py-1 rounded text-sm" data-id="${r.id}">Reject</button>
        </td>
      `;
      leaveTable.appendChild(row);
    });

    document.querySelectorAll(".approve-req").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.currentTarget.getAttribute("data-id");
        if (!id) return;
        await apiCallJSON(`/admin/requests/${id}/approve`, { method: 'POST', body: {} });
        loadRequests();
      });
    });
    document.querySelectorAll(".reject-req").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.currentTarget.getAttribute("data-id");
        if (!id) return;
        await apiCallJSON(`/admin/requests/${id}/reject`, { method: 'POST', body: {} });
        loadRequests();
      });
    });
  } catch (err) {
    console.error("Failed to load requests:", err);
  }
}

// Auto load on page open
// basic loading state
document.getElementById("presentCount").innerText = "...";
document.getElementById("totalStudents").innerText = "...";
document.getElementById("absentCount").innerText = "...";

loadAttendance();
loadRequests();
