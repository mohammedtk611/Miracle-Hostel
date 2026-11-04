/**
 * MIRACLE HOSTEL MANAGEMENT PORTAL - DASHBOARD & INTERACTION SCRIPTS
 * Handles client-side live table filtering, modal population, and confirmation prompts.
 */

document.addEventListener('DOMContentLoaded', function () {
  initClientSideTableFilters();
  initBranchModals();
});

/**
 * Live search and filter for table rows where applicable
 */
function initClientSideTableFilters() {
  const searchInput = document.getElementById('tableLiveSearch');
  const targetTable = document.querySelector('.table-portal tbody');

  if (searchInput && targetTable) {
    searchInput.addEventListener('input', function () {
      const query = searchInput.value.toLowerCase().trim();
      const rows = targetTable.querySelectorAll('tr');

      rows.forEach(function (row) {
        const text = row.textContent.toLowerCase();
        if (text.includes(query)) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  }
}

/**
 * Handle modal data binding for Branch Edit and Deactivate operations
 */
function initBranchModals() {
  // Edit Branch Modal population
  const editModal = document.getElementById('editBranchModal');
  if (editModal) {
    editModal.addEventListener('show.bs.modal', function (event) {
      const button = event.relatedTarget;
      if (!button) return;

      const branchId = button.getAttribute('data-branch-id');
      const branchName = button.getAttribute('data-branch-name');
      const branchCode = button.getAttribute('data-branch-code');
      const branchAddress = button.getAttribute('data-branch-address');
      const branchContact = button.getAttribute('data-branch-contact');

      document.getElementById('edit_branch_id').value = branchId || '';
      document.getElementById('edit_branch_name').value = branchName || '';
      document.getElementById('edit_branch_code').value = branchCode || '';
      document.getElementById('edit_branch_address').value = branchAddress || '';
      document.getElementById('edit_branch_contact').value = branchContact || '';
    });
  }

  // Deactivate Branch Confirmation Dialog
  const deactModal = document.getElementById('deactivateBranchModal');
  if (deactModal) {
    deactModal.addEventListener('show.bs.modal', function (event) {
      const button = event.relatedTarget;
      if (!button) return;

      const branchId = button.getAttribute('data-branch-id');
      const branchName = button.getAttribute('data-branch-name');
      const branchCode = button.getAttribute('data-branch-code');
      const activeCountStr = button.getAttribute('data-active-residents');
      const activeCount = parseInt(activeCountStr || '0', 10);

      document.getElementById('deact_branch_id').value = branchId || '';
      document.getElementById('deact_branch_title').textContent = `${branchName} (${branchCode})`;
      document.getElementById('deact_active_count').textContent = activeCountStr || '0';

      const warningEl = document.getElementById('deact_residents_warning');
      const confirmBtn = document.getElementById('deact_confirm_btn');

      if (activeCount > 0) {
        if (warningEl) warningEl.classList.remove('d-none');
        if (confirmBtn) {
          confirmBtn.disabled = true;
          confirmBtn.classList.add('disabled');
          confirmBtn.title = 'Cannot deactivate branch with active residents';
        }
      } else {
        if (warningEl) warningEl.classList.add('d-none');
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.classList.remove('disabled');
          confirmBtn.title = '';
        }
      }
    });
  }
}

