document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("conference-grid");
  const selectedList = document.getElementById("selected-conferences"); // 없으면 null
  const submitBtn = document.getElementById("submit-btn");
  const form = document.getElementById("filter-form");
  const toggleSelectBtn = document.getElementById("toggle-select-btn");

  // 같은 도메인(8000)에서 서빙하면 빈 문자열로 OK
  const API_BASE = "";
  const API_PREFIX = "/api";

  // ---------------------------
  // util: 선택 리스트 갱신
  // ---------------------------
  function updateSelectedList() {
    if (!selectedList) return;

    const checkboxes = document.querySelectorAll(".conference-checkbox");
    selectedList.innerHTML = "";

    const selected = Array.from(checkboxes)
      .filter((cb) => cb.checked)
      .map((cb) => cb.value);

    selected.forEach((conf) => {
      const li = document.createElement("li");
      li.textContent = conf;
      selectedList.appendChild(li);
    });
  }

  // ---------------------------
  // util: 분야별 버튼 라벨 동기화
  // ---------------------------
  function syncKindToggleButtons() {
    document.querySelectorAll(".card").forEach((card) => {
      const btn = card.querySelector(".kind-toggle-btn");
      const cbs = card.querySelectorAll(".conference-checkbox");
      if (!btn || !cbs.length) return;

      const allChecked = Array.from(cbs).every((cb) => cb.checked);
      btn.textContent = allChecked ? "전체 해제" : "전체 선택";
    });
  }

  // ---------------------------
  // util: 개별 체크박스 change 리스너
  // ---------------------------
  function attachCheckboxListeners() {
    const checkboxes = document.querySelectorAll(".conference-checkbox");
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        updateSelectedList();
        syncKindToggleButtons();
      });
    });
  }

  // ---------------------------
  // 1) 학회 목록 -> 카드/체크박스 생성
  // ---------------------------
  function createCheckboxes(data) {
    const groupedData = data.reduce((acc, row) => {
      const kind = row.kind;
      if (!acc[kind]) acc[kind] = [];
      acc[kind].push(row.conference);
      return acc;
    }, {});

    // 혹시 재렌더링 상황 대비
    grid.innerHTML = "";

    for (const kind in groupedData) {
      const card = document.createElement("div");
      card.classList.add("card");

      const cardTitle = document.createElement("h2");
      cardTitle.textContent = kind;
      card.appendChild(cardTitle);

      const checkboxGroup = document.createElement("div");
      checkboxGroup.classList.add("checkbox-group");

      groupedData[kind].forEach((conference) => {
        const label = document.createElement("label");

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.classList.add("conference-checkbox");
        checkbox.value = conference;

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(conference));
        checkboxGroup.appendChild(label);
      });

      // 카드 하단 전체 선택 버튼
      const kindToggleBtn = document.createElement("button");
      kindToggleBtn.type = "button";
      kindToggleBtn.classList.add("kind-toggle-btn");
      kindToggleBtn.textContent = "전체 선택";

      // append 순서 중요: 그룹 -> 버튼
      card.appendChild(checkboxGroup);
      card.appendChild(kindToggleBtn);
      grid.appendChild(card);

      // 분야별 전체 선택/해제
      kindToggleBtn.addEventListener("click", () => {
        const cbs = checkboxGroup.querySelectorAll(".conference-checkbox");
        if (!cbs.length) return;

        const allChecked = Array.from(cbs).every((cb) => cb.checked);
        const next = !allChecked;

        cbs.forEach((cb) => (cb.checked = next));
        kindToggleBtn.textContent = next ? "전체 해제" : "전체 선택";

        updateSelectedList();
        syncKindToggleButtons();
      });

      // 초기 라벨 세팅
      (() => {
        const cbs = checkboxGroup.querySelectorAll(".conference-checkbox");
        const allChecked = cbs.length > 0 && Array.from(cbs).every((cb) => cb.checked);
        kindToggleBtn.textContent = allChecked ? "전체 해제" : "전체 선택";
      })();
    }

    attachCheckboxListeners();
    updateSelectedList();
    syncKindToggleButtons();
  }

  // 학회 목록 가져오기
  fetch(`${API_BASE}${API_PREFIX}/search/conferences`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => createCheckboxes(data))
    .catch((err) => console.error("Error fetching conference data:", err));

  // ---------------------------
  // 2) 제출 버튼 클릭: FastAPI job 시작
  // ---------------------------
  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      const formData = new FormData(form);
      const filters = Object.fromEntries(formData.entries());

      const selectedRoleEl = document.querySelector('input[name="option"]:checked');
      if (!selectedRoleEl) {
        alert("검색 기준을 하나 선택해주세요");
        return;
      }

      const option = Number(selectedRoleEl.value);

      const selectedConferences = Array.from(document.querySelectorAll(".conference-checkbox"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);

      if (selectedConferences.length === 0) {
        alert("최소 하나 이상의 학회를 선택해주세요!");
        return;
      }

      const startyear = Number(filters.startyear);
      const endyear = Number(filters.endyear);

      if (startyear > endyear) {
        alert("시작 연도는 종료 연도보다 작거나 같아야 합니다");
        return;
      }

      const payload = {
        option,
        uncertainty: Number(filters.uncertainty),
        startyear,
        endyear,
        selectedConferences,
      };

      const resp = await fetch("/api/search/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        alert("검색 시작 실패");
        return;
      }

      const data = await resp.json();
      window.location.href = data.page_url;
    });
  }

  // ---------------------------
  // 3) 전역 모두 선택/해제 버튼
  // ---------------------------
  if (toggleSelectBtn) {
    let allSelected = false;

    toggleSelectBtn.addEventListener("click", () => {
      const checkboxes = document.querySelectorAll(".conference-checkbox");
      allSelected = !allSelected;

      checkboxes.forEach((cb) => {
        cb.checked = allSelected;
      });

      toggleSelectBtn.textContent = allSelected ? "모두 해제" : "모두 선택";

      updateSelectedList();
      syncKindToggleButtons();
    });
  }
});
