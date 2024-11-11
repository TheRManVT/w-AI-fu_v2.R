import { playSongOnTheFly } from "./sing_onthefly";
import { playSongPreprocessed } from "./sing_pproc";

export class Singing {
    static fromPreprocessed = playSongPreprocessed;
    static fromYoutube = playSongOnTheFly;
}
