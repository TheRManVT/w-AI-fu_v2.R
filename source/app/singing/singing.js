"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Singing = void 0;
const sing_onthefly_1 = require("./sing_onthefly");
const sing_pproc_1 = require("./sing_pproc");
class Singing {
    static fromPreprocessed = sing_pproc_1.playSongPreprocessed;
    static fromYoutube = sing_onthefly_1.playSongOnTheFly;
}
exports.Singing = Singing;
