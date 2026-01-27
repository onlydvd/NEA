document.addEventListener('DOMContentLoaded', function () {
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
      var form = document.getElementById('studentForm') || document.querySelector('form');
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

      // required check
      if (input.hasAttribute('required')) {
        if (input.type === 'radio') {
          // check any radio with same name is checked
          var name = input.name;
          var anyChecked = Array.prototype.slice.call(document.querySelectorAll('input[name="' + name + '"]')).some(function (r) { return r.checked; });
          if (!anyChecked) {
            // mark all radios in this group invalid for visual feedback
            var radios = document.querySelectorAll('input[name="' + name + '"]');
            for (var j = 0; j < radios.length; j++) radios[j].classList.add('invalid');
            valid = false;
          }
        } else if (!input.value || input.value.trim() === '') {
          input.classList.add('invalid');
          valid = false;
        }
      }
    }

    // focus first invalid element if any
    var firstInvalid = tab.querySelector('.invalid');
    if (firstInvalid) firstInvalid.focus();

    return valid;
  }

  function fixStepIndicator(n) {
    var steps = document.getElementsByClassName('step');
    for (var i = 0; i < steps.length; i++) {
      steps[i].className = steps[i].className.replace(' active', '');
    }
    if (steps[n]) steps[n].className += ' active';
  }
});
var currentTab = 0; // Current tab is set to be the first tab (0)
showTab(currentTab); // Display the current tab

function showTab(n) {
  // This function will display the specified tab of the form...
  var x = document.getElementsByClassName("tab");
  x[n].style.display = "block";
  //... and fix the Previous/Next buttons:
  if (n == 0) {
    document.getElementById("prevBtn").style.display = "none";
  } else {
    document.getElementById("prevBtn").style.display = "inline";
  }
  if (n == (x.length - 1)) {
    document.getElementById("nextBtn").innerHTML = "Submit";
  } else {
    document.getElementById("nextBtn").innerHTML = "Next";
  }
  //... and run a function that will display the correct step indicator:
  fixStepIndicator(n)
}

function nextPrev(n) {
  // This function will figure out which tab to display
  var x = document.getElementsByClassName("tab");
  // Exit the function if any field in the current tab is invalid:
  if (n == 1 && !validateForm()) return false;
  // Hide the current tab:
  x[currentTab].style.display = "none";
  // Increase or decrease the current tab by 1:
  currentTab = currentTab + n;
  // if you have reached the end of the form...
  if (currentTab >= x.length) {
    // ... the form gets submitted:
    document.getElementById("regForm").submit();
    return false;
  }
  // Otherwise, display the correct tab:
  showTab(currentTab);
}

function validateForm() {
  // This function deals with validation of the form fields
  var x, y, i, valid = true;
  x = document.getElementsByClassName("tab");
  y = x[currentTab].getElementsByTagName("input");
  // A loop that checks every input field in the current tab:
  for (i = 0; i < y.length; i++) {
    // If a field is empty...
    if (y[i].value == "") {
      // add an "invalid" class to the field:
      y[i].className += " invalid";
      // and set the current valid status to false
      valid = false;
    }
  }
  // If the valid status is true, mark the step as finished and valid:
  if (valid) {
    document.getElementsByClassName("step")[currentTab].className += " finish";
  }
  return valid; // return the valid status
}

function fixStepIndicator(n) {
  // This function removes the "active" class of all steps...
  var i, x = document.getElementsByClassName("step");
  for (i = 0; i < x.length; i++) {
    x[i].className = x[i].className.replace(" active", "");
  }
  //... and adds the "active" class on the current step:
  x[n].className += " active";
}