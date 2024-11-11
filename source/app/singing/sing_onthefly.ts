import * as fs from "fs";
import * as cproc from "child_process";
import { ENV } from "../types/Waifu";
import { IO } from "../io/io";
import { RVC } from "../rvc/rvc";

export async function playSongOnTheFly(search_name: string): Promise<void> {
    const DOWNLOADER_PATH = __dirname + "/download_mp3.py";
    const EXTRACTOR_PATH = __dirname + "/extract_vocals.py";

    // RVC sucks and can't escape the spaces in a path so we gotta make a temp
    // folder and move our stuff there
    const temp_path = process.env["LOCALAPPDATA"] + "\\w-AI-fu_v2_tmp";
    if (fs.existsSync(temp_path)) {
        fs.rmSync(temp_path, { recursive: true });
    }

    fs.mkdirSync(temp_path);
    fs.mkdirSync(temp_path + "\\in");
    fs.mkdirSync(temp_path + "\\out");
    fs.mkdirSync(temp_path + "\\voc");
    fs.mkdirSync(temp_path + "\\noecho");

    IO.print("TODO: add parameters to config");
    const min_views = String(10_000);
    const lang = "en";
    const skip_age_res = String(1);

    const downloader = cproc.spawn(
        ENV.PYTHON_PATH,
        [DOWNLOADER_PATH, search_name, min_views, lang, skip_age_res],
        {
            cwd: __dirname,
            env: {
                CWD: process.cwd(),
                LOCALAPPDATA: process.env["LOCALAPPDATA"],
            },
            detached: false,
            shell: false,
        }
    );

    downloader.stdout.on("data", (data) => IO.print(data.toString("utf8")));

    downloader.stderr.on("data", (data: Buffer) => {
        let str = data.toString("utf8");

        // Very bad practice but it not like we have any other choice.
        if (
            !str.toLowerCase().includes("render") &&
            !str.toLowerCase().includes("github")
        ) {
            IO.warn(str);
        }
    });

    let downloader_active = true;
    downloader.on("close", () => {
        downloader_active = false;
    });

    // Yield to event loop until done
    while (downloader_active) {
        await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (downloader.exitCode) {
        IO.warn("ERROR: Failed to download song");
        return;
    }

    IO.print("Extracting vocals...");

    const extractor = cproc.spawn(
        ENV.PYTHON_PATH,
        [EXTRACTOR_PATH, temp_path + "\\in\\audio.wav"],
        {
            cwd: temp_path + "\\out",
            detached: false,
            shell: false,
        }
    );

    extractor.stdout.on("data", (data) => IO.print(data.toString("utf8")));
    extractor.stderr.on("data", (data: Buffer) => {
        let str = data.toString("utf8");

        // Very bad practice but it not like we have any other choice.
        if (!str.toLowerCase().includes("debug")) {
            IO.warn(str);
        }
    });

    let extractor_active = true;
    extractor.on("close", () => {
        extractor_active = false;
    });

    // Yield to event loop until done
    while (extractor_active) {
        await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (extractor.exitCode) {
        IO.warn("ERROR: Failed to extract vocals from song, aborting.");
        return;
    }

    const files = fs.readdirSync(temp_path + "\\out", { encoding: "utf8" });
    let main_vocal_file = files.filter((v) =>
        v.includes("(Vocals)_UVR_MDXNET_KARA.wav")
    )[0];

    if (!main_vocal_file) {
        IO.warn("ERROR: Could not find main vocal audio file, aborting.");
        return;
    }

    fs.copyFileSync(
        temp_path + "\\out\\" + main_vocal_file,
        temp_path + "\\voc\\vocal.wav"
    );

    await RVC.splitTracks(
        "VR-DeEchoNormal",
        temp_path + "\\voc",
        temp_path + "\\noecho",
        "opt"
    );

    const noecho_vocal_file = fs.readdirSync(temp_path + "\\noecho", {
        encoding: "utf8",
    })[0];

    if (!noecho_vocal_file) {
        IO.warn("ERROR: Could not find noecho vocal audio file, aborting.");
        return;
    }

    IO.print("Stems extraction done.");
    IO.print("Using RVC voice inference...");

    // TODO: add index file to config
    await RVC.voiceInfer(
        temp_path + "\\noecho\\" + noecho_vocal_file,
        temp_path + "\\result.wav",
        "C:\\RVC_new\\logs\\HIldaV5\\added_IVF788_Flat_nprobe_1_HIldaV5_v2.index"
    );

    IO.print("Voice inference done.");
}
