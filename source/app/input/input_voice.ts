import * as readline from "readline";
import * as cproc from "child_process";

import { IInputSystem, REJECT_REASON } from "./input_interface";
import { ENV, wAIfu } from "../types/Waifu";
import { Result } from "../types/Result";
import { Message } from "../types/Message";
import { getDeviceIndex } from "../devices/devices";
import { IO } from "../io/io";

import WebSocket, { WebSocketServer } from "ws";

/**
 * Port of the WebSocket server that speech.py sends recognized text to.
 * Change this one value for a different build; speech.py receives it as an argument.
 */
export const STT_PORT = 8711;

export class InputSystemVoice implements IInputSystem {
    #cli_input_interface: readline.Interface;
    #interrupt_next: boolean;

    #child_process: cproc.ChildProcess;
    #websocket_server: WebSocketServer;
    #websocket: WebSocket = new WebSocket(null);

    input_text: string = "";

    constructor() {
        this.#cli_input_interface = readline.createInterface(
            process.stdin,
            process.stdout
        );
        this.#interrupt_next = false;

        let use_ptt =
            wAIfu.state!.config.speech_to_text.push_to_talk.value == true
                ? "1"
                : "0";
        let device = getDeviceIndex(
            wAIfu.state!.config.devices.voice_input_device.value
        ).toString();

        this.#child_process = cproc.spawn(
            ENV.PYTHON_PATH,
            [
                "speech.py",
                use_ptt,
                device,
                wAIfu.state!.config.speech_to_text.stt_provider.value,
                wAIfu.state!.auth.openai.token,
                wAIfu.state!.config.speech_to_text.stt_language.value,
                wAIfu.state!.config.speech_to_text.push_to_talk_key.value,
                wAIfu.state!.config.speech_to_text.toggle_to_talk_key.value,
                STT_PORT.toString(),
            ],
            {
                cwd: `${process.cwd()}/source/app/speech_to_text/`,
                detached: false,
                shell: false,
            }
        );
        this.#child_process.stderr?.on("data", (data) => {
            IO.warn(data.toString());
        });
        this.#child_process.stdout?.on("data", (data) => {
            IO.print(data.toString());
        });

        this.#websocket_server = new WebSocketServer({
            host: "127.0.0.1",
            port: STT_PORT,
        });
    }

    async initialize(): Promise<void> {
        this.#cli_input_interface.removeAllListeners();
        this.#cli_input_interface.on("line", (input) => {
            wAIfu.state!.command_queue.pushBack(input);
        });

        return new Promise((resolve) => {
            this.#websocket_server.on("connection", (socket) => {
                this.#websocket = socket;
                this.#websocket.on("error", (err: Error) => IO.print(err));

                this.#websocket.on("message", (data: WebSocket.RawData) => {
                    let text = data.toString("utf8");
                    if (text == "") {
                        wAIfu.dependencies?.tts.interrupt();
                        return;
                    }
                    this.input_text += text + " ";
                    wAIfu.dependencies?.tts.interrupt();
                    wAIfu.state!.command_queue.pushFront(this.input_text);
                });

                this.#websocket.send("");
                IO.debug("Loaded InputSystemVoice.");
                resolve();
            });
        });
    }

    async free(): Promise<void> {
        this.#cli_input_interface.removeAllListeners();
        this.#cli_input_interface.close();

        return new Promise((resolve) => {
            this.#child_process.on("close", () => {
                this.#child_process.removeAllListeners();
                this.#websocket_server.removeAllListeners();
                this.#websocket.removeAllListeners();
                this.#websocket.close();
                this.#websocket_server.close();

                let el = () => {
                    if (this.#websocket.readyState === WebSocket.CLOSED) {
                        resolve();
                        return;
                    }
                    setTimeout(el, 100);
                };
                setTimeout(el, 100);
            });
            this.#child_process.kill(2);
        });
    }

    interrupt(): void {
        this.#interrupt_next = true;
    }

    async awaitInput(): Promise<Result<Message, REJECT_REASON>> {
        return new Promise<Result<Message, REJECT_REASON>>((resolve) => {
            let resolved = false;

            setTimeout(() => {
                if (resolved === true) return;
                resolved = true;
                resolve(
                    new Result(false, new Message(), REJECT_REASON.TIMEOUT)
                );
                return;
            }, wAIfu.state!.config.live_chat.read_chat_after_x_seconds.value * 1000);

            const check_queue = () => {
                if (this.#interrupt_next === true) {
                    this.#interrupt_next = false;
                    resolve(
                        new Result(
                            false,
                            new Message(),
                            REJECT_REASON.INTERRUPT
                        )
                    );
                    return;
                }
                if (resolved === true) return;
                if (wAIfu.state!.command_queue.notEmpty()) {
                    let message: Message = {
                        sender: wAIfu.state!.config._.user_name.value,
                        content: wAIfu.state!.command_queue.consume(),
                        trusted: true,
                    };
                    resolve(new Result(true, message, REJECT_REASON.NONE));
                    return;
                }
                setTimeout(check_queue, 10);
            };
            check_queue();
        });
    }
}
