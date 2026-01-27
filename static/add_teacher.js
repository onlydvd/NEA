document.addEventListener('DOMContentLoaded', function() {
  var currentTab = 0; // current tab is set to be the first tab (0)
  showTab(currentTab); // display the current tab

  // expose functions used by existing onclick handlers
  window.nextPrev = nextPrev;

  function showTab(n) {
    var tabs = document.getElementsByClassName('tab');
    if (!tabs || tabs.length === 0) return;
    // Hide all tabs
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].style.display = 'none';
    }
    // Show the requested tab
    tabs[n].style.display = 'block';

    // Fix the Previous/Next buttons
    var prevBtn = document.getElementById('prevBtn');
    var nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.style.display = n === 0 ? 'none' : 'inline';
    if (nextBtn) nextBtn.textContent = n === (tabs.length - 1) ? 'Submit' : 'Next';

    // Update step indicators
    fixStepIndicator(n);
  }

  function nextPrev(n) {
    var tabs = document.getElementsByClassName('tab');
    // moving forward, validate the current tab
    if (n === 1 && !validateForm()) return false;

    // hide current tab
    if (tabs[currentTab]) tabs[currentTab].style.display = 'none';

    // change current tab
    currentTab = currentTab + n;

    // if we've reached the end, submit the form
    if (currentTab >= tabs.length) {
      var form = document.getElementById('teacherForm') || document.querySelector('form');
      if (form) form.submit();
      return false;
    }

    // otherwise, display the next tab
    showTab(currentTab);
  }

  function validateForm() {
    var valid = true;
    var tab = document.getElementsByClassName('tab')[currentTab];
    if (!tab) return true;

    // find inputs/selects/textareas inside current tab
    var inputs = tab.querySelectorAll('input, select, textarea');
    for (var i = 0; i < inputs.length; i++) {
      var input = inputs[i];

      // clear previous invalid state
      input.classList.remove('invalid');

      // check for required fields
      if (input.hasAttribute('required') && !input.value) {
        input.classList.add('invalid');
        valid = false;
      }
    }

    // if valid, mark the step as finished
    if (valid) {
      var steps = document.getElementsByClassName('step');
      if (steps[currentTab]) steps[currentTab].classList.add('finish');
    }

    return valid;
  }

  function fixStepIndicator(n) {
    var steps = document.getElementsByClassName('step');
    for (var i = 0; i < steps.length; i++) {
      steps[i].classList.remove('active');
    }
    if (steps[n]) steps[n].classList.add('active');
  }
});