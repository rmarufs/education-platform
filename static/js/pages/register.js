(function() {
    const initialRole = document.currentScript?.dataset.selectedRole || '';
    const form = document.getElementById('register-form');
    const rolePanel = document.getElementById('register-role-panel');
    const selectedRoleInput = document.getElementById('selected-role');
    const selectedRoleLabel = document.getElementById('register-selected-role');
    const studentWizard = document.getElementById('student-wizard');
    const studentSteps = Array.from(document.querySelectorAll('[data-student-step]'));
    const standardSubmit = document.querySelector('.standard-submit-row');
    const teacherFields = document.getElementById('teacher-extra-fields');
    const orgFields = document.getElementById('organization-extra-fields');
    const nameGroup = document.getElementById('name-group');
    const accountFields = Array.from(document.querySelectorAll('[data-account-field]'));
    const studentStep2Actions = document.getElementById('student-step2-actions');
    const teacherOrgSelect = document.getElementById('teacher_org_id');
    const studentOrgPicker = document.getElementById('student-org-picker');
    const studentOrgList = document.getElementById('student-org-list');
    const studentOrgSearch = document.getElementById('student-org-search');
    const studentOrgInput = document.getElementById('student_org_id');
    const studentOrgHint = document.getElementById('student-org-hint');
    const studentPrivacyConsent = document.getElementById('privacy-consent-student');
    const standardPrivacyConsent = document.getElementById('privacy-consent-standard');
    const privacyInputs = Array.from(document.querySelectorAll('input[name="privacy_agreement"]'));
    const totalStudentSteps = 5;
    let studentStep = 1;
    let studentOrgMode = 'skip';
    let organizations = [];
    let orgsLoaded = false;

    const roleLabels = {
        student: 'auth.role_student',
        teacher: 'auth.role_teacher',
        organization: 'auth.role_organization',
    };

    function tr(key, params) {
        return window.t ? t(key, params) : key;
    }

    const serverError = document.getElementById('error-msg');

    function showRole(role) {
        const roleKey = roleLabels[role] || role;
        selectedRoleInput.value = role;
        selectedRoleLabel.setAttribute('data-i18n', roleKey);
        selectedRoleLabel.textContent = tr(roleKey);
        rolePanel.hidden = true;
        form.hidden = false;
        const isStudent = role === 'student';
        const isTeacher = role === 'teacher';
        const isOrg = role === 'organization';

        studentWizard.hidden = !isStudent;
        teacherFields.hidden = !isTeacher;
        orgFields.hidden = !isOrg;
        standardSubmit.hidden = isStudent;
        studentStep2Actions.hidden = !isStudent || studentStep !== 4;
        nameGroup.hidden = isStudent;
        accountFields.forEach((field) => field.hidden = isStudent && studentStep !== 4);
        teacherOrgSelect.disabled = !isTeacher;
        studentPrivacyConsent.hidden = !isStudent || studentStep !== 5;
        standardPrivacyConsent.hidden = isStudent;
        document.getElementById('privacy_agreement_student').disabled = !isStudent;
        document.getElementById('privacy_agreement_standard').disabled = isStudent;

        document.getElementById('gender_student').disabled = !isStudent;
        document.getElementById('gender_teacher').disabled = !isTeacher;

        document.getElementById('org_name').toggleAttribute('required', isOrg);
        document.getElementById('org_phone').toggleAttribute('required', isOrg);
        document.getElementById('org_description').toggleAttribute('required', isOrg);

        if (isTeacher) loadOrganizationsForTeacher();
        if (isStudent) {
            studentStep = 1;
            if (studentOrgInput.value) {
                studentOrgMode = 'choose';
                setStudentOrgMode('choose');
            }
            showStudentStep(1);
        } else {
            studentSteps.forEach((step) => step.hidden = true);
        }
    }

    function showStudentStep(step) {
        studentStep = step;
        studentSteps.forEach((section) => {
            section.hidden = section.dataset.studentStep !== String(step);
        });
        accountFields.forEach((field) => field.hidden = step !== 4);
        studentStep2Actions.hidden = step !== 4;
        studentPrivacyConsent.hidden = step !== 5;
        document.querySelectorAll('[data-step-dot]').forEach((dot) => {
            dot.classList.toggle('is-active', Number(dot.dataset.stepDot) <= step);
        });
        const count = document.getElementById('student-step-count');
        count.textContent = tr('auth.step_count', {current: step, total: totalStudentSteps});
        count.setAttribute('data-i18n-params', JSON.stringify({current: step, total: totalStudentSteps}));
    }

    function setStudentName() {
        const firstName = document.getElementById('first_name').value.trim();
        const lastName = document.getElementById('last_name').value.trim();
        document.getElementById('name').value = [firstName, lastName].filter(Boolean).join(' ');
    }

    function validateStudentStep(step) {
        clearFormErrors(form);
        if (step === 1) {
            const firstName = document.getElementById('first_name');
            const lastName = document.getElementById('last_name');
            const genderStudent = document.getElementById('gender_student');
            let valid = true;
            if (!firstName.value.trim()) {
                showFieldError('first_name', tr('validation.first_name_required'));
                valid = false;
            }
            if (!lastName.value.trim()) {
                showFieldError('last_name', tr('validation.last_name_required'));
                valid = false;
            }
            if (!genderStudent.value) {
                showFieldError('gender_student', tr('validation.gender_required'));
                valid = false;
            }
            if (valid) setStudentName();
            return valid;
        }
        if (step === 2) {
            return validateStudentContactFields();
        }
        if (step === 3) {
            return validateParentContactFields();
        }
        if (step === 4) {
            return validateAccountFields();
        }
        if (step === 5 && studentOrgMode === 'choose' && !studentOrgInput.value) {
            document.getElementById('student-org-error').textContent = tr('validation.organization_required');
            return false;
        }
        return true;
    }

    function validatePrivacyAgreement() {
        privacyInputs.forEach((input) => input.classList.remove('error'));
        const activeInput = privacyInputs.find((input) => !input.disabled);
        if (!activeInput || activeInput.checked) return true;
        showFieldError(activeInput.id, tr('validation.privacy_required'));
        return false;
    }

    function isValidPhone(value) {
        return /^\+?[0-9][0-9\s().-]{6,24}$/.test((value || '').trim());
    }

    function validateStudentContactFields() {
        let valid = true;
        const birthDate = document.getElementById('birth_date');
        const phone = document.getElementById('phone_number');
        if (!birthDate.value) {
            showFieldError('birth_date', tr('validation.birth_date_required'));
            valid = false;
        } else {
            const selectedDate = new Date(`${birthDate.value}T00:00:00`);
            const minDate = new Date('1900-01-01T00:00:00');
            const today = new Date();
            today.setHours(23, 59, 59, 999);
            if (Number.isNaN(selectedDate.getTime()) || selectedDate < minDate || selectedDate > today) {
                showFieldError('birth_date', tr('validation.birth_date_invalid'));
                valid = false;
            }
        }
        if (!phone.value.trim()) {
            showFieldError('phone_number', tr('validation.student_phone_required'));
            valid = false;
        } else if (!isValidPhone(phone.value)) {
            showFieldError('phone_number', tr('auth.invalid_phone'));
            valid = false;
        }
        return valid;
    }

    function validateParentContactFields() {
        let valid = true;
        const parentName = document.getElementById('parent_contact_name');
        const parentPhone = document.getElementById('parent_contact_phone');
        if (!parentName.value.trim()) {
            showFieldError('parent_contact_name', tr('validation.parent_name_required'));
            valid = false;
        }
        if (!parentPhone.value.trim()) {
            showFieldError('parent_contact_phone', tr('validation.parent_phone_required'));
            valid = false;
        } else if (!isValidPhone(parentPhone.value)) {
            showFieldError('parent_contact_phone', tr('auth.invalid_phone'));
            valid = false;
        }
        return valid;
    }

    function validateAccountFields() {
        let valid = true;
        const email = document.getElementById('email');
        const password = document.getElementById('password');
        if (!email.value.trim()) {
            showFieldError('email', tr('validation.email_required'));
            valid = false;
        } else if (!isValidEmail(email.value)) {
            showFieldError('email', tr('validation.email_invalid'));
            valid = false;
        }
        if (!password.value) {
            showFieldError('password', tr('validation.password_required'));
            valid = false;
        } else if (password.value.length < 6) {
            showFieldError('password', tr('validation.password_short'));
            valid = false;
        }
        return valid;
    }

    function loadOrganizations() {
        if (orgsLoaded) return Promise.resolve(organizations);
        orgsLoaded = true;
        return fetch('/api/organizations/list')
            .then((response) => response.json())
            .then((data) => {
                organizations = data.organizations || [];
                return organizations;
            })
            .catch(() => {
                organizations = [];
                return organizations;
            });
    }

    function loadOrganizationsForTeacher() {
        if (teacherOrgSelect.dataset.loaded) return;
        teacherOrgSelect.dataset.loaded = 'true';
        loadOrganizations().then((items) => {
            items.forEach((org) => {
                const option = document.createElement('option');
                option.value = org.id;
                option.textContent = org.name;
                teacherOrgSelect.appendChild(option);
            });
        });
    }

    function renderStudentOrganizations(filterValue) {
        const normalized = (filterValue || '').trim().toLowerCase();
        const filtered = organizations.filter((org) => org.name.toLowerCase().includes(normalized));
        studentOrgList.innerHTML = '';
        filtered.forEach((org) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'student-org-option';
            button.dataset.orgId = org.id;
            button.innerHTML = `
                <span class="student-org-option__name"></span>
                <span class="student-org-option__badge"></span>
            `;
            const badgeKey = org.is_open ? 'auth.open_org' : 'auth.closed_org';
            button.querySelector('.student-org-option__name').textContent = org.name;
            button.querySelector('.student-org-option__badge').setAttribute('data-i18n', badgeKey);
            button.querySelector('.student-org-option__badge').textContent = tr(badgeKey);
            button.classList.toggle('is-selected', studentOrgInput.value === String(org.id));
            button.addEventListener('click', () => selectStudentOrg(org));
            studentOrgList.appendChild(button);
            if (studentOrgInput.value === String(org.id)) {
                const hintKey = org.is_open ? 'auth.joined_org_success' : 'auth.org_request_sent';
                studentOrgHint.setAttribute('data-i18n', hintKey);
                studentOrgHint.textContent = tr(hintKey);
            }
        });
    }

    function selectStudentOrg(org) {
        studentOrgInput.value = org.id;
        document.querySelectorAll('.student-org-option').forEach((button) => {
            button.classList.toggle('is-selected', button.dataset.orgId === String(org.id));
        });
        const hintKey = org.is_open ? 'auth.joined_org_success' : 'auth.org_request_sent';
        studentOrgHint.setAttribute('data-i18n', hintKey);
        studentOrgHint.textContent = tr(hintKey);
        document.getElementById('student-org-error').textContent = '';
    }

    function setStudentOrgMode(mode) {
        studentOrgMode = mode;
        document.querySelectorAll('[data-student-org-mode]').forEach((button) => {
            button.classList.toggle('is-active', button.dataset.studentOrgMode === mode);
        });
        studentOrgPicker.hidden = mode !== 'choose';
        if (mode === 'skip') {
            studentOrgInput.value = '';
            document.getElementById('student-org-error').textContent = '';
            studentOrgHint.setAttribute('data-i18n', 'auth.application_will_be_sent');
            studentOrgHint.textContent = tr('auth.application_will_be_sent');
        } else {
            loadOrganizations().then(() => renderStudentOrganizations(studentOrgSearch.value));
        }
    }

    document.querySelectorAll('[data-register-role]').forEach((button) => {
        button.addEventListener('click', () => showRole(button.dataset.registerRole));
    });

    document.getElementById('register-change-role').addEventListener('click', () => {
        form.hidden = true;
        rolePanel.hidden = false;
        selectedRoleInput.value = '';
    });

    document.querySelectorAll('[data-student-next]').forEach((button) => {
        button.addEventListener('click', () => {
            if (validateStudentStep(studentStep)) showStudentStep(studentStep + 1);
        });
    });

    document.querySelectorAll('[data-student-back]').forEach((button) => {
        button.addEventListener('click', () => showStudentStep(Math.max(1, studentStep - 1)));
    });

    document.querySelectorAll('[data-student-org-mode]').forEach((button) => {
        button.addEventListener('click', () => setStudentOrgMode(button.dataset.studentOrgMode));
    });

    studentOrgSearch.addEventListener('input', () => renderStudentOrganizations(studentOrgSearch.value));
    document.getElementById('first_name').addEventListener('input', setStudentName);
    document.getElementById('last_name').addEventListener('input', setStudentName);

    form.addEventListener('submit', (event) => {
        const role = selectedRoleInput.value;
        if (!role) {
            event.preventDefault();
            rolePanel.hidden = false;
            form.hidden = true;
            return;
        }
        if (role === 'student') {
            setStudentName();
            for (let step = 1; step <= totalStudentSteps; step += 1) {
                if (!validateStudentStep(step)) {
                    event.preventDefault();
                    showStudentStep(step);
                    return;
                }
            }
        }
        if (!validatePrivacyAgreement()) {
            event.preventDefault();
            if (role === 'student') showStudentStep(5);
            return;
        }
    });

    function applyServerError() {
        if (!serverError) return;
        const key = serverError.dataset.errorKey;
        const message = key ? tr(key) : serverError.textContent;
        if (key) serverError.textContent = message;
        const step = Number(serverError.dataset.errorStep);
        if (selectedRoleInput.value === 'student' && step) showStudentStep(step);
        const field = serverError.dataset.errorField;
        if (!field) return;
        if (field === 'student_org_id') {
            document.getElementById('student-org-error').textContent = message;
        } else if (field === 'gender') {
            // Map the generic 'gender' field error to the specific role input
            if (selectedRoleInput.value === 'student') {
                showFieldError('gender_student', message);
            } else if (selectedRoleInput.value === 'teacher') {
                showFieldError('gender_teacher', message);
            }
        } else if (field === 'privacy_agreement_student') {
            showStudentStep(5);
            showFieldError(field, message);
        } else {
            showFieldError(field, message);
        }
    }

    if (initialRole) showRole(initialRole);
    applyServerError();
})();
