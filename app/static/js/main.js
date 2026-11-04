/**
 * MIRACLE HOSTEL MANAGEMENT PORTAL - CORE JAVASCRIPT
 * Vanilla JS interactions: Sidebar, Password toggle, Image preview, Aadhaar formatting, Toasts.
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Sidebar Toggle for Desktop and Mobile
  initSidebar();

  // 2. Password Visibility Toggle
  initPasswordToggles();

  // 3. Image Upload Live Preview
  initImagePreviews();

  // 4. Aadhaar Input Formatting and Validation
  initAadhaarInputs();

  // 5. Global Branch Selector Navigation
  initBranchSelectors();

  // 6. Initialize Bootstrap Toasts
  initToasts();

  // 7. Table Action Dropdowns Anti-Clipping & Max Z-Index
  initTableDropdowns();

  // 8. Dark / Light Theme Mode Switcher
  initThemeToggle();
});

/**
 * Sidebar collapsing and mobile drawer handler
 */
function initSidebar() {
  const sidebar = document.querySelector('.app-sidebar');
  const desktopToggle = document.getElementById('sidebarDesktopToggle');
  const mobileToggle = document.getElementById('mobileMenuToggle');
  const mobileClose = document.getElementById('sidebarMobileClose');
  const backdrop = document.getElementById('sidebarBackdrop');

  function openMobileSidebar() {
    if (!sidebar || !backdrop) return;
    sidebar.classList.add('show-mobile');
    backdrop.classList.add('active');
    document.body.classList.add('sidebar-open-mobile');
    document.body.style.overflow = 'hidden';
  }

  function closeMobileSidebar() {
    if (!sidebar || !backdrop) return;
    sidebar.classList.remove('show-mobile');
    backdrop.classList.remove('active');
    document.body.classList.remove('sidebar-open-mobile');
    document.body.style.overflow = '';
  }

  if (desktopToggle) {
    desktopToggle.addEventListener('click', function () {
      document.body.classList.toggle('sidebar-collapsed');
      const isCollapsed = document.body.classList.contains('sidebar-collapsed');
      localStorage.setItem('miracle_sidebar_collapsed', isCollapsed ? '1' : '0');
    });

    // Restore desktop preference
    if (localStorage.getItem('miracle_sidebar_collapsed') === '1' && window.innerWidth >= 992) {
      document.body.classList.add('sidebar-collapsed');
    }
  }

  if (mobileToggle) {
    mobileToggle.addEventListener('click', function (e) {
      e.preventDefault();
      openMobileSidebar();
    });
  }

  if (mobileClose) {
    mobileClose.addEventListener('click', function (e) {
      e.preventDefault();
      closeMobileSidebar();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', function () {
      closeMobileSidebar();
    });
  }

  // Close sidebar on link click in mobile view
  if (sidebar) {
    sidebar.querySelectorAll('.nav-link-portal, .brand-link').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth < 992) {
          closeMobileSidebar();
        }
      });
    });
  }

  // Close mobile drawer on Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('show-mobile')) {
      closeMobileSidebar();
    }
  });

  // Automatically reset mobile state if viewport is resized to desktop
  window.addEventListener('resize', function () {
    if (window.innerWidth >= 992 && sidebar && sidebar.classList.contains('show-mobile')) {
      closeMobileSidebar();
    }
  });
}

/**
 * Toggle visibility of password inputs
 */
function initPasswordToggles() {
  const toggleButtons = document.querySelectorAll('[data-toggle="password"]');
  toggleButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';

      // Update button icon or text
      const icon = btn.querySelector('i');
      if (icon) {
        if (isPassword) {
          icon.classList.remove('bi-eye');
          icon.classList.add('bi-eye-slash');
        } else {
          icon.classList.remove('bi-eye-slash');
          icon.classList.add('bi-eye');
        }
      }
    });
  });
}

/**
 * Image upload live preview with FileReader
 */
function initImagePreviews() {
  const photoInputs = document.querySelectorAll('input[type="file"][data-preview-target]');
  photoInputs.forEach(function (input) {
    input.addEventListener('change', function () {
      const targetSelector = input.getAttribute('data-preview-target');
      const previewImg = document.querySelector(targetSelector);
      const placeholder = document.querySelector(input.getAttribute('data-placeholder-target'));

      if (input.files && input.files[0]) {
        const file = input.files[0];
        // Enforce max 5MB in UI
        if (file.size > 5 * 1024 * 1024) {
          alert('Image size exceeds 5MB limit. Please choose a smaller photograph.');
          input.value = '';
          return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
          if (previewImg) {
            previewImg.src = e.target.result;
            previewImg.classList.remove('d-none');
          }
          if (placeholder) {
            placeholder.classList.add('d-none');
          }
        };
        reader.readAsDataURL(file);
      }
    });
  });
}

/**
 * Aadhaar formatting (XXXX XXXX XXXX) and client validation
 * Strict Security Constraint: Aadhaar numbers are never stored in browser local storage.
 */
function initAadhaarInputs() {
  const aadhaarInputs = document.querySelectorAll('input[data-aadhaar-input]');
  aadhaarInputs.forEach(function (input) {
    // Disable autocomplete and caching
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('spellcheck', 'false');

    input.addEventListener('input', function (e) {
      let value = input.value.replace(/\D/g, ''); // Digits only
      if (value.length > 12) {
        value = value.substring(0, 12);
      }

      // Format as 4-digit groups: 1234 5678 9012
      let formatted = '';
      for (let i = 0; i < value.length; i++) {
        if (i > 0 && i % 4 === 0) {
          formatted += ' ';
        }
        formatted += value[i];
      }
      input.value = formatted;

      // Validation feedback
      const feedback = document.getElementById(input.getAttribute('data-feedback-target'));
      if (feedback) {
        if (value.length === 12) {
          if (value.startsWith('0') || value.startsWith('1')) {
            feedback.textContent = 'Aadhaar cannot start with 0 or 1.';
            feedback.className = 'form-text text-danger';
          } else {
            feedback.textContent = `Valid 12-digit format. Encrypted at rest (Only ending in ${value.substring(8)} displayed).`;
            feedback.className = 'form-text text-success';
          }
        } else if (value.length > 0) {
          feedback.textContent = `${12 - value.length} more digits required.`;
          feedback.className = 'form-text text-muted';
        } else {
          feedback.textContent = 'Enter 12-digit UIDAI number. Will be encrypted at rest using AES-256.';
          feedback.className = 'form-text text-muted';
        }
      }
    });
  });
}

/**
 * Topbar Branch selector handler to trigger dynamic page updates
 */
function initBranchSelectors() {
  const branchSelect = document.getElementById('globalBranchSelect');
  if (branchSelect) {
    branchSelect.addEventListener('change', function () {
      const selectedValue = branchSelect.value;
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('branch', selectedValue);
      // Reset search page parameter if present
      currentUrl.searchParams.delete('page');
      window.location.href = currentUrl.toString();
    });
  }
}

/**
 * Bootstrap Toasts initialization
 */
function initToasts() {
  const toastElList = [].slice.call(document.querySelectorAll('.toast'));
  if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
    toastElList.map(function (toastEl) {
      const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
      toast.show();
      return toast;
    });
  }
}

/**
 * Table Action Dropdowns - Floating Fixed Strategy & Anti-Clipping
 * Ensures action dropdowns in tables float over all containers, footers, and viewports.
 */
function initTableDropdowns() {
  function configureDropdown(btn) {
    if (typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
      bootstrap.Dropdown.getOrCreateInstance(btn, {
        popperConfig: function (defaultBsPopperConfig) {
          return Object.assign({}, defaultBsPopperConfig, {
            strategy: 'fixed'
          });
        }
      });
    }
  }

  // Configure all current table dropdown toggles
  document.querySelectorAll(
    '.table-portal [data-bs-toggle="dropdown"], .table-portal-responsive [data-bs-toggle="dropdown"], [data-table-dropdown]'
  ).forEach(configureDropdown);

  // Global document listener for any dynamically rendered or static table dropdowns
  document.addEventListener('show.bs.dropdown', function (e) {
    const toggle = e.target;
    if (!toggle) return;
    
    // Check if dropdown is inside a table or responsive container
    const tableContainer = toggle.closest('.table-responsive-portal, .table-responsive');
    if (tableContainer) {
      tableContainer.classList.add('dropdown-open-unclip');
      tableContainer.style.setProperty('overflow', 'visible', 'important');
      
      const cardBody = tableContainer.closest('.card-portal-body');
      if (cardBody) {
        cardBody.style.setProperty('overflow', 'visible', 'important');
      }
      const card = tableContainer.closest('.card-portal');
      if (card) {
        card.style.setProperty('overflow', 'visible', 'important');
      }
      const row = toggle.closest('tr');
      if (row) {
        row.style.setProperty('z-index', '999999', 'important');
        row.style.setProperty('position', 'relative', 'important');
      }
      const cell = toggle.closest('td');
      if (cell) {
        cell.style.setProperty('z-index', '999999', 'important');
        cell.style.setProperty('position', 'relative', 'important');
      }
      
      const menu = toggle.nextElementSibling && toggle.nextElementSibling.classList.contains('dropdown-menu')
        ? toggle.nextElementSibling
        : (toggle.parentElement ? toggle.parentElement.querySelector('.dropdown-menu') : null);
      if (menu) {
        menu.style.setProperty('z-index', '9999999', 'important');
      }
    }
  });

  document.addEventListener('hidden.bs.dropdown', function (e) {
    const toggle = e.target;
    if (!toggle) return;

    const tableContainer = toggle.closest('.table-responsive-portal, .table-responsive');
    if (tableContainer) {
      tableContainer.classList.remove('dropdown-open-unclip');
      tableContainer.style.removeProperty('overflow');
      
      const cardBody = tableContainer.closest('.card-portal-body');
      if (cardBody) {
        cardBody.style.removeProperty('overflow');
      }
      const card = tableContainer.closest('.card-portal');
      if (card) {
        card.style.removeProperty('overflow');
      }
      const row = toggle.closest('tr');
      if (row) {
        row.style.removeProperty('z-index');
        row.style.removeProperty('position');
      }
      const cell = toggle.closest('td');
      if (cell) {
        cell.style.removeProperty('z-index');
        cell.style.removeProperty('position');
      }
    }
  });
}

/**
 * Dark / Light Theme Mode Switcher
 * Provides persistent toggle between Light and Dark mode with anti-FOUC and system preference support.
 */
function initThemeToggle() {
  const toggleButtons = document.querySelectorAll('.theme-toggle-btn, #themeToggleBtn');
  const dropdownBtn = document.getElementById('themeToggleDropdownBtn');

  function getActiveTheme() {
    return document.documentElement.getAttribute('data-bs-theme') || 
           localStorage.getItem('miracle_theme') || 
           (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);

    const metaScheme = document.querySelector('meta[name="color-scheme"]');
    if (metaScheme) {
      metaScheme.content = theme;
    }

    // Update Topbar Toggle Button Icon
    const darkIcons = document.querySelectorAll('.theme-icon-dark');
    const lightIcons = document.querySelectorAll('.theme-icon-light');
    const modeLabels = document.querySelectorAll('.theme-mode-label');

    if (theme === 'dark') {
      darkIcons.forEach(el => el.classList.add('d-none'));
      lightIcons.forEach(el => el.classList.remove('d-none'));
      modeLabels.forEach(el => {
        el.textContent = 'On';
        el.className = 'badge bg-success-subtle text-success small theme-mode-label';
      });
      toggleButtons.forEach(btn => {
        btn.setAttribute('title', 'Switch to Light Theme');
      });
    } else {
      darkIcons.forEach(el => el.classList.remove('d-none'));
      lightIcons.forEach(el => el.classList.add('d-none'));
      modeLabels.forEach(el => {
        el.textContent = 'Off';
        el.className = 'badge bg-secondary-subtle text-secondary small theme-mode-label';
      });
      toggleButtons.forEach(btn => {
        btn.setAttribute('title', 'Switch to Dark Theme');
      });
    }
  }

  function toggleTheme() {
    const currentTheme = getActiveTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('miracle_theme', newTheme);
    } catch (e) {}
    applyTheme(newTheme);
  }

  toggleButtons.forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      toggleTheme();
    });
  });

  if (dropdownBtn) {
    dropdownBtn.addEventListener('click', function (e) {
      e.preventDefault();
      toggleTheme();
    });
  }

  // Sync across browser tabs
  window.addEventListener('storage', function (e) {
    if (e.key === 'miracle_theme' && e.newValue) {
      applyTheme(e.newValue);
    }
  });

  // Listen to OS system preference changes if no explicit user override is stored
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
      if (!localStorage.getItem('miracle_theme')) {
        applyTheme(e.matches ? 'dark' : 'light');
      }
    });
  }

  // Initial UI state setup
  applyTheme(getActiveTheme());
}

