"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.playSongOnTheFly = void 0;
const fs = __importStar(require("fs"));
const cproc = __importStar(require("child_process"));
const Waifu_1 = require("../types/Waifu");
const io_1 = require("../io/io");
const rvc_1 = require("../rvc/rvc");
async function playSongOnTheFly(search_name) {
    const DOWNLOADER_PATH = __dirname + "/download_mp3.py";
    const EXTRACTOR_PATH = __dirname + "/extract_vocals.py";
    const temp_path = process.env["LOCALAPPDATA"] + "\\w-AI-fu_v2_tmp";
    if (fs.existsSync(temp_path)) {
        fs.rmSync(temp_path, { recursive: true });
    }
    fs.mkdirSync(temp_path);
    fs.mkdirSync(temp_path + "\\in");
    fs.mkdirSync(temp_path + "\\out");
    fs.mkdirSync(temp_path + "\\voc");
    fs.mkdirSync(temp_path + "\\noecho");
    io_1.IO.print("TODO: add parameters to config");
    const min_views = String(10_000);
    const lang = "en";
    const skip_age_res = String(1);
    const downloader = cproc.spawn(Waifu_1.ENV.PYTHON_PATH, [DOWNLOADER_PATH, search_name, min_views, lang, skip_age_res], {
        cwd: __dirname,
        env: {
            CWD: process.cwd(),
            LOCALAPPDATA: process.env["LOCALAPPDATA"],
        },
        detached: false,
        shell: false,
    });
    downloader.stdout.on("data", (data) => io_1.IO.print(data.toString("utf8")));
    downloader.stderr.on("data", (data) => {
        let str = data.toString("utf8");
        if (!str.toLowerCase().includes("render") &&
            !str.toLowerCase().includes("github")) {
            io_1.IO.warn(str);
        }
    });
    let downloader_active = true;
    downloader.on("close", () => {
        downloader_active = false;
    });
    while (downloader_active) {
        await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (downloader.exitCode) {
        io_1.IO.warn("ERROR: Failed to download song");
        return;
    }
    io_1.IO.print("Extracting vocals...");
    const extractor = cproc.spawn(Waifu_1.ENV.PYTHON_PATH, [EXTRACTOR_PATH, temp_path + "\\in\\audio.wav"], {
        cwd: temp_path + "\\out",
        detached: false,
        shell: false,
    });
    extractor.stdout.on("data", (data) => io_1.IO.print(data.toString("utf8")));
    extractor.stderr.on("data", (data) => {
        let str = data.toString("utf8");
        if (!str.toLowerCase().includes("debug")) {
            io_1.IO.warn(str);
        }
    });
    let extractor_active = true;
    extractor.on("close", () => {
        extractor_active = false;
    });
    while (extractor_active) {
        await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (extractor.exitCode) {
        io_1.IO.warn("ERROR: Failed to extract vocals from song, aborting.");
        return;
    }
    const files = fs.readdirSync(temp_path + "\\out", { encoding: "utf8" });
    let main_vocal_file = files.filter((v) => v.includes("(Vocals)_UVR_MDXNET_KARA.wav"))[0];
    if (!main_vocal_file) {
        io_1.IO.warn("ERROR: Could not find main vocal audio file, aborting.");
        return;
    }
    fs.copyFileSync(temp_path + "\\out\\" + main_vocal_file, temp_path + "\\voc\\vocal.wav");
    await rvc_1.RVC.splitTracks("VR-DeEchoNormal", temp_path + "\\voc", temp_path + "\\noecho", "opt");
    const noecho_vocal_file = fs.readdirSync(temp_path + "\\noecho", {
        encoding: "utf8",
    })[0];
    if (!noecho_vocal_file) {
        io_1.IO.warn("ERROR: Could not find noecho vocal audio file, aborting.");
        return;
    }
    io_1.IO.print("Stems extraction done.");
    io_1.IO.print("Using RVC voice inference...");
    await rvc_1.RVC.voiceInfer(temp_path + "\\noecho\\" + noecho_vocal_file, temp_path + "\\result.wav", "C:\\RVC_new\\logs\\HIldaV5\\added_IVF788_Flat_nprobe_1_HIldaV5_v2.index");
    io_1.IO.print("Voice inference done.");
}
exports.playSongOnTheFly = playSongOnTheFly;
