const campaignEditModal = document.querySelector("[data-campaign-edit-modal]");
const openCampaignEditButton = document.querySelector("[data-open-campaign-edit]");
const campaignCoverInput = document.querySelector("[data-campaign-cover-input]");
const campaignCoverFile = document.querySelector("[data-campaign-cover-file]");

function openCampaignEditModal() {
  if (!campaignEditModal) return;
  campaignEditModal.classList.add("is-open");
  campaignEditModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => campaignEditModal.querySelector("input[name='name']")?.focus(), 40);
}

function closeCampaignEditModal() {
  if (!campaignEditModal) return;
  campaignEditModal.classList.remove("is-open");
  campaignEditModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("has-modal");
}

openCampaignEditButton?.addEventListener("click", openCampaignEditModal);
campaignCoverInput?.addEventListener("change", () => {
  if (!campaignCoverFile) return;
  campaignCoverFile.textContent = campaignCoverInput.files?.[0]?.name || "PNG, JPG, WEBP, GIF, AVIF";
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-campaign-edit]")) {
    closeCampaignEditModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeCampaignEditModal();
  }
});
