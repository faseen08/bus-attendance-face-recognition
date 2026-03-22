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

let adminAttendanceRecords = null;
let adminAllStudents = null;
let adminTotalStudentsFallback = 0;

function formatDateDisplay(value) {
  if (!value) return value;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }
  return value;
}

function parseDisplayDateToISO(value) {
  if (!value) return "";
  const match = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return "";
  const [, day, month, year] = match;
  return `${year}-${month}-${day}`;
}

function formatISOToDisplay(value) {
  return formatDateDisplay(value);
}

function getSelectedAttendanceDateISO() {
  const dateInput = document.getElementById("dateInput");
  if (!dateInput) return new Date().toISOString().slice(0, 10);
  if (!dateInput.value) {
    const todayISO = new Date().toISOString().slice(0, 10);
    dateInput.value = formatDateDisplay(todayISO);
    return todayISO;
  }
  const parsed = parseDisplayDateToISO(dateInput.value);
  return parsed || new Date().toISOString().slice(0, 10);
}

async function loadAttendance() {
  try {
    const needsReload = !Array.isArray(adminAttendanceRecords) || !Array.isArray(adminAllStudents);
    if (needsReload) {
      // Fetch attendance, student count, and student list for filters.
      const [data, countJson, students] = await Promise.all([
        apiCallJSON('/attendance'),
        apiCallJSON('/students/count'),
        apiCallJSON('/students')
      ]);

      if (!data || !countJson) {
        throw new Error('Failed to load data');
      }

      adminAttendanceRecords = Array.isArray(data) ? data : [];
      adminAllStudents = Array.isArray(students) ? students : [];
      adminTotalStudentsFallback = typeof countJson.count === 'number' ? countJson.count : 0;

      adminSetSelectOptions(document.getElementById("adminFilterCollegeYear"), COLLEGE_YEARS, "All Years");
      adminSetSelectOptions(
        document.getElementById("adminFilterCollegeDept"),
        [...new Set(adminAllStudents.map(s => (s.college_department || '').trim()).filter(Boolean))],
        "All Departments"
      );
      adminSetSelectOptions(document.getElementById("adminFilterSchoolClass"), SCHOOL_CLASSES, "All Classes");
      adminSetSelectOptions(
        document.getElementById("adminFilterSchoolDivision"),
        [...new Set(adminAllStudents.map(s => (s.school_division || '').trim()).filter(Boolean))],
        "All Divisions"
      );
      adminUpdateFilterVisibility();
    }

    renderAttendance();
  } catch (err) {
    console.error("Failed to load attendance or students:", err);
    document.getElementById("presentCount").innerText = "–";
    document.getElementById("totalStudents").innerText = "–";
    document.getElementById("absentCount").innerText = "–";
  }
}

async function loadDriverPunches() {
  const dateInput = document.getElementById("driverPunchDateInput");
  let selectedDate = dateInput?.value || "";
  
  // Convert DD/MM/YYYY to YYYY-MM-DD if needed
  if (selectedDate && selectedDate.includes("/")) {
    const [day, month, year] = selectedDate.split("/");
    selectedDate = `${year}-${month}-${day}`;
  }
  
  // Default to today if no date selected
  if (!selectedDate) {
    selectedDate = new Date().toISOString().slice(0, 10);
  }
  
  const table = document.getElementById("driverPunchTable");
  if (!table) return;

  try {
    const res = await apiCallJSON(`/admin/driver-shifts?date=${encodeURIComponent(selectedDate)}`);
    if (!res || res.error) throw new Error(res?.error || "Failed to load driver shifts");
    table.innerHTML = "";
    res.shifts.forEach((s) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="p-3">${s.driver_id}</td>
        <td class="p-3">${s.driver_name || '--'}</td>
        <td class="p-3">${s.bus_number || '--'}</td>
        <td class="p-3">${s.punch_in_at || '--'}</td>
        <td class="p-3">${s.punch_out_at || '--'}</td>
        <td class="p-3">${s.status || '--'}</td>
      `;
      table.appendChild(row);
    });
  } catch (err) {
    console.error("Failed to load driver punches:", err);
    table.innerHTML = `<tr><td class="p-3 text-slate-400" colspan="6">Failed to load driver punches.</td></tr>`;
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
      const leaveDate = payload.date_display || formatDateDisplay(payload.date) || "-";
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="p-3">${payload.student_id || r.requester_id}</td>
        <td class="p-3">${desired}</td>
        <td class="p-3 text-slate-300 text-sm">${leaveDate}</td>
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
        const res = await apiCallJSON(`/admin/requests/${id}/approve`, { method: 'POST', body: {} });
        if (res?.error) {
          alert(res.error);
          return;
        }
        loadRequests();
      });
    });
    document.querySelectorAll(".reject-req").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.currentTarget.getAttribute("data-id");
        if (!id) return;
        const res = await apiCallJSON(`/admin/requests/${id}/reject`, { method: 'POST', body: {} });
        if (res?.error) {
          alert(res.error);
          return;
        }
        loadRequests();
      });
    });
  } catch (err) {
    console.error("Failed to load requests:", err);
  }
}

// Student attendance filters (admin dashboard)
const COLLEGE_YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year"];
const SCHOOL_CLASSES = [
  "Pre-Primary",
  "LKG",
  "UKG",
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "11",
  "12"
];

function adminSetSelectOptions(select, values, placeholder) {
  if (!select) return;
  select.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = placeholder;
  select.appendChild(defaultOption);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function adminUpdateFilterVisibility() {
  const type = document.getElementById("adminFilterEducationType")?.value || "";
  const showCollege = type === "" || type === "college";
  const showSchool = type === "" || type === "school";
  document.getElementById("adminFilterCollegeYearWrap")?.classList.toggle("hidden", !showCollege);
  document.getElementById("adminFilterCollegeDeptWrap")?.classList.toggle("hidden", !showCollege);
  document.getElementById("adminFilterSchoolClassWrap")?.classList.toggle("hidden", !showSchool);
  document.getElementById("adminFilterSchoolDivWrap")?.classList.toggle("hidden", !showSchool);
}

function adminFilterStudents(students) {
  const type = document.getElementById("adminFilterEducationType")?.value || "";
  const collegeYear = document.getElementById("adminFilterCollegeYear")?.value || "";
  const collegeDept = document.getElementById("adminFilterCollegeDept")?.value || "";
  const schoolClass = document.getElementById("adminFilterSchoolClass")?.value || "";
  const schoolDivision = document.getElementById("adminFilterSchoolDivision")?.value || "";

  return students.filter((s) => {
    if (type && (s.education_type || "") !== type) return false;
    if (collegeYear && (s.college_year || "") !== collegeYear) return false;
    if (collegeDept && (s.college_department || "") !== collegeDept) return false;
    if (schoolClass && (s.school_class || "") !== schoolClass) return false;
    if (schoolDivision && (s.school_division || "") !== schoolDivision) return false;
    return true;
  });
}

function renderAttendance() {
  const table = document.getElementById("attendanceTable");
  if (!table) return;
  const selectedDate = getSelectedAttendanceDateISO();

  const filteredStudents = adminFilterStudents(adminAllStudents || []);
  const filteredIds = new Set(filteredStudents.map((s) => s.student_id));
  const dateRecords = (adminAttendanceRecords || []).filter(
    (r) => r.date === selectedDate && filteredIds.has(r.student_id)
  );

  table.innerHTML = "";
  if (dateRecords.length === 0) {
    table.innerHTML = `<tr><td class="p-3 text-slate-400" colspan="4">No records for selected filters/date.</td></tr>`;
  } else {
    dateRecords.forEach((record) => {
      const row = document.createElement("tr");
      const tripLabel = record.trip_type === "TO_SCHOOL"
        ? "To School"
        : record.trip_type === "TO_HOME"
          ? "To Home"
          : "--";
      row.innerHTML = `
        <td class="p-3">${record.student_id}</td>
        <td class="p-3">${formatDateDisplay(record.date)}</td>
        <td class="p-3">${record.time}</td>
        <td class="p-3">${tripLabel}</td>
        <td class="p-3 text-green-400 font-semibold">Present</td>
      `;
      table.appendChild(row);
    });
  }

  const presentIds = new Set(dateRecords.map((r) => r.student_id));
  const totalStudents = filteredStudents.length || adminTotalStudentsFallback;
  document.getElementById("presentCount").innerText = presentIds.size;
  document.getElementById("totalStudents").innerText = totalStudents;
  document.getElementById("absentCount").innerText = Math.max(0, totalStudents - presentIds.size);
}

// Auto load on page open
// basic loading state
document.getElementById("presentCount").innerText = "...";
document.getElementById("totalStudents").innerText = "...";
document.getElementById("absentCount").innerText = "...";

// Initialize date inputs with today's date
const today = new Date().toISOString().slice(0, 10);
const dateInputElem = document.getElementById("dateInput");
if (dateInputElem && !dateInputElem.value) {
  dateInputElem.value = formatDateDisplay(today);
}
const driverDateInputElem = document.getElementById("driverPunchDateInput");
if (driverDateInputElem && !driverDateInputElem.value) {
  driverDateInputElem.value = formatDateDisplay(today);
}

loadAttendance();
loadRequests();
loadDriverPunches();

// Admin dashboard toggles
const studentAttendancePanel = document.getElementById("studentAttendancePanel");
const driverAttendancePanel = document.getElementById("driverAttendancePanel");
document.getElementById("toggleStudentAttendance")?.addEventListener("click", () => {
  studentAttendancePanel?.classList.remove("hidden");
  driverAttendancePanel?.classList.add("hidden");
  loadAttendance();
});
document.getElementById("toggleDriverAttendance")?.addEventListener("click", () => {
  studentAttendancePanel?.classList.add("hidden");
  driverAttendancePanel?.classList.remove("hidden");
  loadDriverPunches();
});

document.getElementById("adminFilterEducationType")?.addEventListener("change", () => {
  adminUpdateFilterVisibility();
  renderAttendance();
});
document.getElementById("adminFilterCollegeYear")?.addEventListener("change", () => renderAttendance());
document.getElementById("adminFilterCollegeDept")?.addEventListener("change", () => renderAttendance());
document.getElementById("adminFilterSchoolClass")?.addEventListener("change", () => renderAttendance());
document.getElementById("adminFilterSchoolDivision")?.addEventListener("change", () => renderAttendance());
document.getElementById("adminResetFilters")?.addEventListener("click", () => {
  document.getElementById("adminFilterEducationType").value = "";
  document.getElementById("adminFilterCollegeYear").value = "";
  document.getElementById("adminFilterCollegeDept").value = "";
  document.getElementById("adminFilterSchoolClass").value = "";
  document.getElementById("adminFilterSchoolDivision").value = "";
  adminUpdateFilterVisibility();
  renderAttendance();
});

const datePickerBtn = document.getElementById("datePickerBtn");
const dateInput = document.getElementById("dateInput");
const datePicker = document.getElementById("customDatePicker");
const datePickerGrid = document.getElementById("datePickerGrid");
const datePickerLabel = document.getElementById("datePickerLabel");
const datePickerPrev = document.getElementById("datePickerPrev");
const datePickerNext = document.getElementById("datePickerNext");

let pickerMonth = new Date();

function renderDatePicker() {
  if (!datePickerGrid || !datePickerLabel) return;
  const year = pickerMonth.getFullYear();
  const month = pickerMonth.getMonth();
  const monthName = pickerMonth.toLocaleString(undefined, { month: "long" });
  datePickerLabel.textContent = `${monthName} ${year}`;

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  datePickerGrid.innerHTML = "";
  for (let i = 0; i < firstDay; i++) {
    const blank = document.createElement("div");
    datePickerGrid.appendChild(blank);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "p-1 rounded hover:bg-slate-700 text-slate-200 text-sm";
    btn.textContent = String(day);
    btn.addEventListener("click", () => {
      const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      if (dateInput) {
        dateInput.value = formatISOToDisplay(iso);
      }
      datePicker?.classList.add("hidden");
      loadAttendance();
    });
    datePickerGrid.appendChild(btn);
  }
}

if (datePickerBtn && datePicker) {
  datePickerBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    datePicker.classList.toggle("hidden");
    renderDatePicker();
  });
}

datePickerPrev?.addEventListener("click", (e) => {
  e.stopPropagation();
  pickerMonth = new Date(pickerMonth.getFullYear(), pickerMonth.getMonth() - 1, 1);
  renderDatePicker();
});

datePickerNext?.addEventListener("click", (e) => {
  e.stopPropagation();
  pickerMonth = new Date(pickerMonth.getFullYear(), pickerMonth.getMonth() + 1, 1);
  renderDatePicker();
});

document.addEventListener("click", (e) => {
  if (!datePicker || datePicker.classList.contains("hidden")) return;
  if (datePicker.contains(e.target) || datePickerBtn?.contains(e.target)) return;
  datePicker.classList.add("hidden");
});

// Driver Punch Date Picker
const driverDatePickerBtn = document.getElementById("driverDatePickerBtn");
const driverDateInput = document.getElementById("driverPunchDateInput");
const driverDatePicker = document.getElementById("driverCustomDatePicker");
const driverDatePickerGrid = document.getElementById("driverDatePickerGrid");
const driverDatePickerLabel = document.getElementById("driverDatePickerLabel");
const driverDatePickerPrev = document.getElementById("driverDatePickerPrev");
const driverDatePickerNext = document.getElementById("driverDatePickerNext");

let driverPickerMonth = new Date();

function renderDriverDatePicker() {
  if (!driverDatePickerGrid || !driverDatePickerLabel) return;
  const year = driverPickerMonth.getFullYear();
  const month = driverPickerMonth.getMonth();
  const monthName = driverPickerMonth.toLocaleString(undefined, { month: "long" });
  driverDatePickerLabel.textContent = `${monthName} ${year}`;

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  driverDatePickerGrid.innerHTML = "";
  for (let i = 0; i < firstDay; i++) {
    const blank = document.createElement("div");
    driverDatePickerGrid.appendChild(blank);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "p-1 rounded hover:bg-slate-700 text-slate-200 text-sm";
    btn.textContent = String(day);
    btn.addEventListener("click", () => {
      const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      if (driverDateInput) {
        driverDateInput.value = formatISOToDisplay(iso);
      }
      driverDatePicker?.classList.add("hidden");
      loadDriverPunches();
    });
    driverDatePickerGrid.appendChild(btn);
  }
}

if (driverDatePickerBtn && driverDatePicker) {
  driverDatePickerBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    driverDatePicker.classList.toggle("hidden");
    renderDriverDatePicker();
  });
}

driverDatePickerPrev?.addEventListener("click", (e) => {
  e.stopPropagation();
  driverPickerMonth = new Date(driverPickerMonth.getFullYear(), driverPickerMonth.getMonth() - 1, 1);
  renderDriverDatePicker();
});

driverDatePickerNext?.addEventListener("click", (e) => {
  e.stopPropagation();
  driverPickerMonth = new Date(driverPickerMonth.getFullYear(), driverPickerMonth.getMonth() + 1, 1);
  renderDriverDatePicker();
});

document.addEventListener("click", (e) => {
  if (!driverDatePicker || driverDatePicker.classList.contains("hidden")) return;
  if (driverDatePicker.contains(e.target) || driverDatePickerBtn?.contains(e.target)) return;
  driverDatePicker.classList.add("hidden");
});

const toggleBtn = document.getElementById("toggleRequestsBtn");
const requestsPanel = document.getElementById("requestsPanel");
if (toggleBtn && requestsPanel) {
  toggleBtn.addEventListener("click", () => {
    requestsPanel.classList.toggle("hidden");
    if (!requestsPanel.classList.contains("hidden")) {
      loadRequests();
    }
  });
}
