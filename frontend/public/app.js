"use strict";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = {
  jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png",
  gif: "image/gif", webp: "image/webp",
};

const $ = (id) => document.getElementById(id);
const form = $("upload-form");
const fileInput = $("photo");
const captionInput = $("caption");
const passwordInput = $("password");
const button = $("upload-btn");
const formError = $("form-error");
const wall = $("wall");
const wallMessage = $("wall-message");

try { passwordInput.value = sessionStorage.getItem("uploadPassword") || ""; } catch (e) {}

captionInput.addEventListener("input", () => {
  $("caption-count").textContent = captionInput.value.length + "/200";
});

function timeAgo(iso) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  const units = [["day", 86400], ["hour", 3600], ["minute", 60]];
  if (seconds < 60) return "just now";
  for (const [name, size] of units) {
    if (seconds >= size) {
      const n = Math.floor(seconds / size);
      return n + " " + name + (n === 1 ? "" : "s") + " ago";
    }
  }
}

let photos = [];
let current = -1;

function makeTile(photo) {
  const tile = document.createElement("button");
  tile.type = "button";
  tile.className = "tile";
  tile.setAttribute("aria-label", "Open photo: " + photo.caption);
  tile.addEventListener("click", () => openViewer(photos.indexOf(photo)));

  const img = document.createElement("img");
  img.loading = "lazy";
  img.src = photo.imageUrl;
  img.alt = photo.caption;

  const caption = document.createElement("span");
  caption.className = "tile-caption";
  caption.textContent = photo.caption;

  tile.append(img, caption);
  return tile;
}

function renderWall() {
  wall.replaceChildren(...photos.map(makeTile));
  wallMessage.replaceChildren();
  if (!photos.length) {
    const title = document.createElement("strong");
    title.textContent = "No photos yet";
    wallMessage.append(title, "Tap “New post” to share the first one.");
  }
}

function showSkeletons() {
  wall.replaceChildren(...Array.from({ length: 9 }, () => {
    const s = document.createElement("div");
    s.className = "tile skeleton";
    return s;
  }));
}

/* viewer */
const viewer = $("viewer");
const viewerImg = $("viewer-img");
const prevBtn = $("viewer-prev");
const nextBtn = $("viewer-next");

function showPhoto(i) {
  current = i;
  const p = photos[i];
  viewerImg.src = p.imageUrl;
  viewerImg.alt = p.caption;
  $("viewer-caption").textContent = p.caption;
  const t = $("viewer-time");
  t.textContent = timeAgo(p.uploadedAt);
  t.dateTime = p.uploadedAt;
  prevBtn.hidden = i === 0;
  nextBtn.hidden = i === photos.length - 1;
}

function openViewer(i) {
  if (i < 0) return;
  showPhoto(i);
  viewer.showModal();
}

prevBtn.addEventListener("click", () => { if (current > 0) showPhoto(current - 1); });
nextBtn.addEventListener("click", () => { if (current < photos.length - 1) showPhoto(current + 1); });
$("close-viewer").addEventListener("click", () => viewer.close());
viewer.addEventListener("click", (e) => { if (e.target === viewer) viewer.close(); });
viewer.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") prevBtn.click();
  if (e.key === "ArrowRight") nextBtn.click();
});

/* upload dialog */
const uploadDialog = $("upload-dialog");
const preview = $("preview");

function resetForm() {
  fileInput.value = "";
  captionInput.value = "";
  $("caption-count").textContent = "0/200";
  formError.textContent = "";
  preview.hidden = true;
  if (preview.src) URL.revokeObjectURL(preview.src);
  preview.removeAttribute("src");
  $("dropzone").classList.remove("has-image");
}

$("open-upload").addEventListener("click", () => uploadDialog.showModal());
$("close-upload").addEventListener("click", () => uploadDialog.close());
uploadDialog.addEventListener("click", (e) => { if (e.target === uploadDialog) uploadDialog.close(); });

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (preview.src) URL.revokeObjectURL(preview.src);
  if (!file) { preview.hidden = true; $("dropzone").classList.remove("has-image"); return; }
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  $("dropzone").classList.add("has-image");
});

let retrying = false;

async function loadWall() {
  try {
    const res = await fetch("/api/photos", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    photos = data.photos;
    renderWall();
    if (retrying) { retrying = false; loadServers(); }
  } catch (e) {
    retrying = true;
    wall.replaceChildren();
    wallMessage.textContent = "The photo wall is having trouble right now. Retrying...";
    setTimeout(loadWall, 5000);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";

  const file = fileInput.files[0];
  const caption = captionInput.value.trim();
  if (!file) { formError.textContent = "Please choose a photo"; return; }
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  if (!TYPES[ext] || TYPES[ext] !== file.type) {
    formError.textContent = "Only JPEG, PNG, GIF or WebP images are allowed";
    return;
  }
  if (file.size > MAX_BYTES) { formError.textContent = "That file is too big (5 MB maximum)"; return; }
  if (caption.length < 1 || caption.length > 200) {
    formError.textContent = "Caption must be 1 to 200 characters";
    return;
  }

  const password = passwordInput.value;
  try { sessionStorage.setItem("uploadPassword", password); } catch (e) {}

  const body = new FormData();
  body.append("photo", file);
  body.append("caption", caption);

  button.disabled = true;
  button.textContent = "Uploading...";
  try {
    const res = await fetch("/api/photos", {
      method: "POST",
      headers: { "X-Upload-Password": password },
      body,
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.status === 201) {
      resetForm();
      uploadDialog.close();
      photos.unshift(data);
      renderWall();
    } else {
      formError.textContent = data.error || "Upload failed, please try again";
    }
  } catch (e) {
    formError.textContent = "Upload failed, please try again";
  } finally {
    button.disabled = false;
    button.textContent = "Share";
  }
});

async function fetchInfo(url) {
  try {
    const sep = url.includes("?") ? "&" : "?";
    const res = await fetch(url + sep + "t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const d = await res.json();
    return d.instanceId + " (" + d.zone + ")";
  } catch (e) {
    return "unavailable";
  }
}

async function loadServers() {
  const [front, back] = await Promise.all([fetchInfo("/frontend-info"), fetchInfo("/api/info")]);
  $("server-info").textContent = "Frontend " + front + " · Backend " + back;
}

$("refresh-servers").addEventListener("click", (event) => {
  event.preventDefault();
  loadServers();
});

showSkeletons();
loadWall();
loadServers();
