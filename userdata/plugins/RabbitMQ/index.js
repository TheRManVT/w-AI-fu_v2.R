"use strict";

// @ts-ignore
const amqp = require("amqplib/callback_api");
const fs = require("fs");

/** @type { {print:(...args: any[])=> void, warn:(...args: any[])=> void} } */
let logger = { print: (..._) => {}, warn: (..._) => {} };

let held_msg = "";
let consumed = "";

/** @type { any|undefined } */
let config = undefined;

/** @type { any|undefined } */
let amqp_connection = undefined;

/** @type { any|undefined } */
let amqp_channel = undefined;

/** @param { any } passed_logger */
exports.onLoad = (passed_logger) => {
    logger = passed_logger;
    logger.print("Loaded RabbitMQ plugin.");

    config = JSON.parse(
        fs.readFileSync(__dirname + "/config.json", { encoding: "utf8" })
    );

    amqp.connect(
        config.host_url,
        /** @param { Error } error0 @param { any } connection */
        (error0, connection) => {
            if (error0) {
                if (error0.message.includes("ECONNREFUSED")) {
                    logger.warn("RabbitMQ: error: Could not connect to host.");
                }
                return;
            }
            logger.print("Connected to RabbitMQ server.");
            amqp_connection = connection;
            connection.createChannel(
                /** @param { Error } error1 @param { any } channel */
                (error1, channel) => {
                    if (error1) {
                        throw error1;
                    }
                    amqp_channel = channel;
                }
            );
        }
    );
};

exports.onInputQuery = () => {
    // @ts-ignore
    if (amqp_channel === undefined) return undefined;

    if (consumed !== "") {
        let ret_val = consumed;
        consumed = "";
        return ret_val.trim();
    }

    // @ts-ignore
    amqp_channel.consume(
        config.other_queue,
        (msg) => {
            let str_msg = msg.content.toString();
            logger.print("RabbitMQ: received:", str_msg);
            consumed = str_msg;
        },
        {
            noAck: true,
        }
    );
    return undefined;
};

/**
 * @param { string } response
 */
exports.onResponse = (response) => {
    // @ts-ignore
    if (amqp_channel === undefined) return;
    held_msg = response;
    logger.print("RabbitMQ: queuing:", held_msg);
};

exports.onMainLoopEnd = () => {
    // @ts-ignore
    if (amqp_channel === undefined) return;
    if (held_msg === "") return;
    // @ts-ignore
    amqp_channel.assertQueue(config.queue, {
        durable: false,
    });
    // @ts-ignore
    amqp_channel.sendToQueue(config.queue, Buffer.from(held_msg));

    logger.print("RabbitMQ: sent:", held_msg);
    held_msg = "";
};

exports.onQuit = () => {
    amqp_channel = undefined;
    amqp_connection = undefined;
};
