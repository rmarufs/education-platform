const groupModeModal = document.getElementById("group-mode-modal");
const groupModeName = document.getElementById("group-mode-name");
const groupModeManage = document.getElementById("group-mode-manage");
const groupModeTeach = document.getElementById("group-mode-teach");
const groupModeReview = document.getElementById("group-mode-review");

function openGroupModeModal(trigger) {
    if (!groupModeModal || !trigger) return;
    groupModeName.textContent = trigger.dataset.groupName || "";
    groupModeManage.href = trigger.dataset.manageUrl || "#";
    groupModeTeach.href = trigger.dataset.teachUrl || "#";
    groupModeReview.href = trigger.dataset.reviewUrl || "#";
    groupModeModal.classList.add("is-open");
    groupModeModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("group-mode-lock");
    groupModeManage.focus();
}

function closeGroupModeModal() {
    if (!groupModeModal) return;
    groupModeModal.classList.remove("is-open");
    groupModeModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("group-mode-lock");
}

document.querySelectorAll("[data-group-mode-close]").forEach((item) => {
    item.addEventListener("click", closeGroupModeModal);
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && groupModeModal?.classList.contains("is-open")) {
        closeGroupModeModal();
    }
});
