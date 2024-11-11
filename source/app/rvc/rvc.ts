import * as fs from "fs";

import { IO } from "../io/io";

const TIMEOUT = 300_000;

export class RVC {
    static voiceInfer(
        input_audio_path: string,
        output_path: string,
        index_file_path: string = ""
    ): Promise<boolean> {
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
                        0, // ID
                        input_audio_path, // File path for conversion
                        0, // Pitch correction
                        null, // f0 file
                        "pm", // model
                        "", // ?
                        index_file_path, // index file
                        0.85, // accent
                        3, // f0 filter
                        0, // resampling
                        0.5, // volume envelope
                        0.3, // breathiness
                    ],
                }),
            })
                .then((response) => {
                    response.json().then(
                        (val) => {
                            if (is_resolved === true) return;
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
                        },
                        (reason) => IO.error(reason)
                    );
                })
                .catch((reason) => IO.error(reason));

            const timeout = () => {
                if (is_resolved === true) return;
                is_resolved = true;
                IO.warn("ERROR: RVC voice inference timed out.");
                resolve(false);
                return;
            };
            setTimeout(timeout, TIMEOUT);
        });
    }

    static async splitTracks(
        model_name: string,
        input_audio_path: string,
        first_output_folder_path: string,
        second_output_folder_path: string
    ): Promise<void> {
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
                    r.json().then(
                        (r) => {
                            IO.print(input_audio_path);
                            if (is_resolved) return;
                            IO.print(r.data);
                            is_resolved = true;
                            resolve();
                            return;
                        },
                        (reason) => IO.error(reason)
                    );
                })
                .catch((reason) => IO.error(reason));
        });
    }
}
