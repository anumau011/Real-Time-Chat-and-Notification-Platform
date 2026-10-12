// /home/eddy/projects/chat/realtime_chat/static/js/emoji-picker.js
import * as EmojiMart from '@emoji-mart/js';

class EmojiPicker {
    constructor(options) {
        this.picker = new EmojiMart.Picker({
            ...options,
            data: async () => {
                const response = await fetch('https://cdn.jsdelivr.net/npm/@emoji-mart/data');
                return response.json();
            }
        });
    }

    togglePicker(button) {
        this.picker.toggle(button);
    }
}