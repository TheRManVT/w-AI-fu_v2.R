"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatStampedMemory = formatStampedMemory;
function formatStampedMemory(memory) {
    const now_ms = Date.now();
    const diff_ms = now_ms - memory.timestamp;
    const diff_minutes = Math.floor(diff_ms / (1000 * 60));
    const diff_hours = Math.floor(diff_ms / (1000 * 60 * 60));
    const diff_days = Math.floor(diff_ms / (1000 * 60 * 60 * 24));
    const diff_months = Math.floor(diff_days / 30.44);
    const diff_years = Math.floor(diff_days / 365.25);
    let time_frame;
    if (diff_years >= 1) {
        time_frame = `(${diff_years} year${diff_years > 1 ? "s" : ""} ago) `;
    }
    else if (diff_months >= 1) {
        time_frame = `(${diff_months} month${diff_months > 1 ? "s" : ""} ago) `;
    }
    else if (diff_days >= 1) {
        time_frame = `(${diff_days} day${diff_days > 1 ? "s" : ""} ago) `;
    }
    else if (diff_hours >= 1) {
        time_frame = `(${diff_hours} hour${diff_hours > 1 ? "s" : ""} ago) `;
    }
    else if (diff_minutes >= 1) {
        time_frame = `(${diff_minutes} minute${diff_minutes > 1 ? "s" : ""} ago) `;
    }
    else {
        time_frame = "(less than a minute ago) ";
    }
    return time_frame + memory.content;
}