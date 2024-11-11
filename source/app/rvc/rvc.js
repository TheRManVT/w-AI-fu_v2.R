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
exports.RVC = void 0;
const fs = __importStar(require("fs"));
const io_1 = require("../io/io");
const TIMEOUT = 300_000;
class RVC {
    static voiceInfer(input_audio_path, output_path, index_file_path = "") {
        return new Promise((resolve) => {
            let is_resolved = false;
            fetch("http://127.0.0.1:7897/run/infer_convert", {
                method: "POST",
                headers: {
                    accept: "*/*",
                    "accept-language": "en-US,en;q=0.9",
                    "content-type": "application/json",
                },
                body: JSON.stringify({
                    data: [
                        0,
                        input_audio_path,
                        0,
                        null,
                        "pm",
                        "",
                        index_file_path,
                        0.85,
                        3,
                        0,
                        0.5,
                        0.3,
                    ],
                }),
            })
                .then((response) => {
                response.json().then((val) => {
                    if (is_resolved === true)
                        return;
                    if (!val["data"] || !val["data"][1]) {
                        is_resolved = true;
                        resolve(false);
                        return;
                    }
                    let file = val["data"][1]["name"];
                    let data = fs.readFileSync(file);
                    fs.writeFileSync(output_path, data);
                    is_resolved = true;
                    resolve(true);
                }, (reason) => io_1.IO.error(reason));
            })
                .catch((reason) => io_1.IO.error(reason));
            const timeout = () => {
                if (is_resolved === true)
                    return;
                is_resolved = true;
                io_1.IO.warn("ERROR: RVC voice inference timed out.");
                resolve(false);
                return;
            };
            setTimeout(timeout, TIMEOUT);
        });
    }
    static async splitTracks(model_name, input_audio_path, first_output_folder_path, second_output_folder_path) {
        return new Promise((resolve) => {
            let is_resolved = false;
            fetch("http://127.0.0.1:7897/run/uvr_convert", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    data: [
                        model_name,
                        input_audio_path,
                        first_output_folder_path,
                        null,
                        second_output_folder_path,
                        5,
                        "wav",
                    ],
                }),
            })
                .then((r) => {
                r.json().then((r) => {
                    io_1.IO.print(input_audio_path);
                    if (is_resolved)
                        return;
                    io_1.IO.print(r.data);
                    is_resolved = true;
                    resolve();
                    return;
                }, (reason) => io_1.IO.error(reason));
            })
                .catch((reason) => io_1.IO.error(reason));
        });
    }
}
exports.RVC = RVC;
