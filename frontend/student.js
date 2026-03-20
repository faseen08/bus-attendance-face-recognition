/**
 * Students List - Main Script
 * 
 * This handles loading and displaying the list of students
 * Features:
 * - Loads all students from backend
 * - Displays student photo, name, ID, and leave status
 * - Uses authenticated API calls (includes JWT token automatically)
 */

// This will be set by api.js when included
// const API_BASE and other utilities come from api.js

let allStudents = [];
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

function uniqueValues(items, key) {
  const set = new Set();
  items.forEach((item) => {
    const value = (item[key] || "").toString().trim();
    if (value) set.add(value);
  });
  return Array.from(set).sort();
}

function setSelectOptions(select, values, placeholder) {
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

function updateFilterVisibility() {
  const type = document.getElementById("filterEducationType")?.value || "";
  const showCollege = type === "" || type === "college";
  const showSchool = type === "" || type === "school";
  document.getElementById("filterCollegeYearWrap")?.classList.toggle("hidden", !showCollege);
  document.getElementById("filterCollegeDeptWrap")?.classList.toggle("hidden", !showCollege);
  document.getElementById("filterSchoolClassWrap")?.classList.toggle("hidden", !showSchool);
  document.getElementById("filterSchoolDivWrap")?.classList.toggle("hidden", !showSchool);
}

function applyFilters(students) {
  const type = document.getElementById("filterEducationType")?.value || "";
  const collegeYear = document.getElementById("filterCollegeYear")?.value || "";
  const collegeDept = document.getElementById("filterCollegeDept")?.value || "";
  const schoolClass = document.getElementById("filterSchoolClass")?.value || "";
  const schoolDivision = document.getElementById("filterSchoolDivision")?.value || "";

  return students.filter((s) => {
    if (type && (s.education_type || "") !== type) return false;
    if (collegeYear && (s.college_year || "") !== collegeYear) return false;
    if (collegeDept && (s.college_department || "") !== collegeDept) return false;
    if (schoolClass && (s.school_class || "") !== schoolClass) return false;
    if (schoolDivision && (s.school_division || "") !== schoolDivision) return false;
    return true;
  });
}

function renderStudents(students) {
  const table = document.getElementById("studentsTable");
  if (!table) return;
  table.innerHTML = "";

  students.forEach((s) => {
    const row = document.createElement("tr");
    row.className = "hover:bg-slate-700/50 transition-colors border-b border-slate-700";

    const educationText = s.education_type === "college"
      ? `${s.college_year || "Year?"} ${s.college_department || "Dept?"}`.trim()
      : s.education_type === "school"
        ? `${s.school_class || "Class?"} • ${s.school_division || "Division?"}`
        : "Not set";

    row.innerHTML = `
      <td class="p-3">
        <img src="${API_BASE}/${s.photo_path}" class="h-12 w-12 object-cover rounded-full border border-slate-600">
      </td>
      <td class="p-3">
        <div class="font-bold text-slate-200">${s.name || s.student_id}</div>
        <div class="text-xs text-slate-500">${s.student_id}</div>
      </td>
      <td class="p-3 text-slate-300 text-sm">
        ${educationText}
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
      <td class="p-3 text-sm">
        <button class="delete-student bg-red-700 hover:bg-red-600 px-3 py-1 rounded text-white text-xs" data-student-id="${s.student_id}">
          Delete
        </button>
      </td>
      `;
    table.appendChild(row);
  });

  document.querySelectorAll(".delete-student").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      const studentId = event.currentTarget.getAttribute("data-student-id");
      if (!studentId) return;
      const confirmed = confirm(`Delete student ${studentId}? This cannot be undone.`);
      if (!confirmed) return;

      try {
        const response = await apiCall(`/students/${studentId}`, { method: "DELETE" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Delete failed");
        }
        allStudents = allStudents.filter((s) => s.student_id !== studentId);
        renderStudents(applyFilters(allStudents));
      } catch (err) {
        console.error("Failed to delete student:", err);
        alert(`Failed to delete student: ${err.message}`);
      }
    });
  });
}

async function loadStudents() {
  try {
    // Use apiCallJSON() to load students with token included automatically
    const students = await apiCallJSON('/students');

    if (!students) {
      throw new Error('Failed to load students data');
    }

    allStudents = students;

    setSelectOptions(document.getElementById("filterCollegeYear"), COLLEGE_YEARS, "All Years");
    setSelectOptions(document.getElementById("filterCollegeDept"), uniqueValues(students, "college_department"), "All Departments");
    setSelectOptions(document.getElementById("filterSchoolClass"), SCHOOL_CLASSES, "All Classes");
    setSelectOptions(document.getElementById("filterSchoolDivision"), uniqueValues(students, "school_division"), "All Divisions");

    updateFilterVisibility();
    renderStudents(applyFilters(allStudents));
  } catch (err) {
    console.error("Failed to load students:", err);
  }
}

// Don't forget to call the function!
document.getElementById("filterEducationType")?.addEventListener("change", () => {
  updateFilterVisibility();
  renderStudents(applyFilters(allStudents));
});
document.getElementById("filterCollegeYear")?.addEventListener("change", () => renderStudents(applyFilters(allStudents)));
document.getElementById("filterCollegeDept")?.addEventListener("change", () => renderStudents(applyFilters(allStudents)));
document.getElementById("filterSchoolClass")?.addEventListener("change", () => renderStudents(applyFilters(allStudents)));
document.getElementById("filterSchoolDivision")?.addEventListener("change", () => renderStudents(applyFilters(allStudents)));
document.getElementById("resetFilters")?.addEventListener("click", () => {
  document.getElementById("filterEducationType").value = "";
  document.getElementById("filterCollegeYear").value = "";
  document.getElementById("filterCollegeDept").value = "";
  document.getElementById("filterSchoolClass").value = "";
  document.getElementById("filterSchoolDivision").value = "";
  updateFilterVisibility();
  renderStudents(applyFilters(allStudents));
});

loadStudents();
