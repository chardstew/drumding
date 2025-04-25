import tkinter as tk
from tkinter import messagebox
import mido
import time

# ── GLOBAL CONFIGURATION & PRE-MEASURE ───────────────────────────────
MAX_TOTAL_STEPS    = 64
MIDI_PORT_NAME     = 'gord 1'
INSTRUMENTS        = [
    "crash1", "china", "tom3", "tom2",
    "tom 1", "ghosties", "snare", "kick",
    "crash2", "bell ride", "ping ride", "wash ride",
    "clamp", "closed hat", "open hat", "aux"
]

COLORS = {
    'bg':              'black',
    'on':              '#00ff00',    # full velocity bright green
    'half':            '#008800',    # half velocity shade
    'off':             '#668866',
    'disabled':        '#111111',
    'section_border':  '#666666',
    'text':            'white',
    'highlight':       '#FDE8AC',
    'blue':            '#0165FC',
    'red':             '#FF0000',
}

DEFAULT_NOTES = {
    "crash1":     48, "china":      51, "tom3":       46, "tom2":       45,
    "tom 1":      44, "ghosties":   39, "snare":      38, "kick":       36,
    "crash2":     50, "bell ride":  42, "ping ride":  41, "wash ride":  40,
    "clamp":      None, "closed hat": 43, "open hat":   47, "aux":        None,
}

# Measure a single button width once
_hidden = tk.Tk(); _hidden.withdraw()
_frame  = tk.Frame(_hidden)
_btn    = tk.Button(_frame, width=2, height=1, relief='flat')
_btn.pack(); _hidden.update_idletasks()
BTN_W    = _btn.winfo_reqwidth()
_hidden.destroy()
CELL_TOTAL = BTN_W + 2
TOTAL_W    = CELL_TOTAL * 32

class InstrumentRow:
    def __init__(self, parent, name, sequencer):
        self.sequencer        = sequencer
        self.name             = name

        # ── DATA STORAGE ───────────────────────────────────────────────
        # full 64-step pattern: 'off', 'half', 'on', or 'disabled'
        self.pattern          = ['off'] * 64
        # each 16-step block can be masked on/off
        self.segment_mask     = [True, True, False, False]
        # how far to pan the window (–16…+16)
        self.shift_offset     = 0
        # computed for playback: list of (r, c, color) tuples
        self.sequence_positions = []
        # mute toggle
        self.muted            = False

        # ── UI CONTAINER & HEADER ──────────────────────────────────────
        self.frame = tk.Frame(
            parent, bg=COLORS['bg'],
            highlightbackground=COLORS['section_border'],
            highlightthickness=1,
            width=TOTAL_W + 12
        )
        self.frame.pack_propagate(False)
        self.header = tk.Frame(self.frame, bg=COLORS['bg'])
        self.header.pack(fill='x', pady=2)

        # Update track name label styling
        self.name_label = tk.Label(
            self.header, text=name,
            bg=COLORS['bg'], fg=COLORS['text'],  # Same background/foreground as the popup
            font=('Fixedsys', 12),  # Fixedsys font, 12 size (similar to popup label)
            width=12, anchor='w'
        )
        self.name_label.pack(side='left', padx=(8, 0))
        self.name_label.bind('<Double-Button-1>', lambda e: self.toggle_mute())
        self.name_label.bind('<Control-Button-1>', lambda e: self.sequencer._solo(self))
        self.name_label.pack(side='left', padx=(8,0))
        self.name_label.bind('<Double-Button-1>', lambda e: self.toggle_mute())
        self.name_label.bind('<Control-Button-1>', lambda e: self.sequencer._solo(self))

        # ── segment-mask buttons ───────────────────────────────────────
        seg_frame = tk.Frame(self.header, bg=COLORS['bg'])
        seg_frame.pack(side='left', padx=4)
        self.seg_btns = []
        for i in range(4):
            btn = tk.Button(
                seg_frame, text=str(i + 1),
                width=2, height=1,
                bg=('#9D00FF' if self.segment_mask[i] else COLORS['section_border']),
                fg=COLORS['text'], relief='flat',
                font=('Fixedsys', 12),  # Fixedsys font with size 12
                command=lambda i=i: self.toggle_segment(i)
            )
            btn.pack(side='left', padx=1)
            self.seg_btns.append(btn)

        # Minus and Plus Buttons for shifting
        self.shift_left_btn = tk.Button(
            self.header, text='–', width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['text'], relief='flat',
            font=('Fixedsys', 12),  # Fixedsys font with size 12
            command=lambda: self.shift(-1)
        )
        self.shift_left_btn.pack(side='left', padx=(6, 0))

        self.shift_right_btn = tk.Button(
            self.header, text='+', width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['text'], relief='flat',
            font=('Fixedsys', 12),  # Fixedsys font with size 12
            command=lambda: self.shift(1)
        )
        self.shift_right_btn.pack(side='left')

        # Update "every" dropdown menu styling
        every = tk.Menubutton(
            self.header, text="every",
            bg=COLORS['bg'], fg=COLORS['blue'],  # Matching background and text colors
            relief='flat', direction='below',
            font=('Fixedsys', 12)  # Use Fixedsys font with size 12 for consistency
        )

        # Create the menu
        menu = tk.Menu(every, tearoff=0, bg=COLORS['bg'], fg=COLORS['text'], font=('Fixedsys', 12))

        # Add menu items
        for n in range(1, 17):  # Add options 1-16 to the menu
            menu.add_command(
                label=str(n),
                command=lambda n=n: self.apply_every(n)
            )

        # Configure each menu item with appropriate colors
        for item in menu.winfo_children():
            item.config(
                bg=COLORS['bg'],  # Background color for the menu
                fg=COLORS['text'],  # Text color for the menu items
                activebackground=COLORS['highlight'],  # Highlight color when an item is selected
                activeforeground=COLORS['text'],  # Text color when an item is selected
            )

        # Attach the menu to the Menubutton
        every.configure(menu=menu)
        every.pack(side='left', padx=(6, 0))



        # spacer + note entry + clear bomb
        tk.Frame(self.header, bg=COLORS['bg']).pack(side='left', fill='x', expand=True)
        self.note_var = tk.StringVar()
        tk.Entry(
            self.header, textvariable=self.note_var,
            width=4, bg='black', fg='white', justify='left',
            font=('Fixedsys', 12)  # Fixedsys font with size 12
        ).pack(side='right', padx=8)
        default = DEFAULT_NOTES.get(name)
        if default is not None:
            self.note_var.set(str(default))
        self.clear_btn = tk.Button(
            self.header, text='💣', width=3, height=1,
            bg=COLORS['bg'], fg=COLORS['red'], relief='flat',
            command=self.clear_track
        )
        self.clear_btn.pack(side='right', padx=(2,0))

        # ── build static 2×32 button grid ─────────────────────────────
        self.grid_frame = tk.Frame(self.frame, bg=COLORS['bg'])
        self.grid_frame.pack(anchor='w', padx=6)
        self.row_frames = [tk.Frame(self.grid_frame, bg=COLORS['bg']) for _ in range(2)]
        for rf in self.row_frames:
            rf.pack(anchor='w')

        self.step_buttons = [[], []]
        for r in range(2):
            for c in range(32):
                b = tk.Button(
                    self.row_frames[r], width=2, height=1,
                    bg=COLORS['off'], relief='flat'
                )
                b.bind('<Button-1>',           lambda e, r=r, c=c: self._on_toggle(r,c))
                b.bind('<Control-Button-1>',    lambda e, r=r, c=c: self._on_half(r,c))
                b.bind('<Double-Button-1>',     lambda e, r=r, c=c: self._on_disable(r,c))
                self.step_buttons[r].append(b)

        # initial draw + height fix
        self.refresh_display()
        self.frame.update_idletasks()
        header_h = self.header.winfo_reqheight()
        row_h    = self.row_frames[0].winfo_reqheight()
        self.frame.config(height=header_h + row_h*2 + 8)

    def refresh_display(self):
        for r in (0,1):
            for c, b in enumerate(self.step_buttons[r]):
                b.grid_forget()
                if r == 1 and self.sequencer.half_mode:
                    continue

                idx = r*32 + c


                if not self.segment_mask[idx//16]:
                    color = COLORS['disabled']
                else:
                    state = self.pattern[idx]
                    color = COLORS.get(state, COLORS['off'])

                b.config(bg=color)
                b.grid(in_=self.row_frames[r], row=0, column=c, padx=1, pady=1)

        self.update_positions()




    def toggle_segment(self, i):
        self.segment_mask[i] = not self.segment_mask[i]
        self.seg_btns[i].config(
            bg=('#9D00FF' if self.segment_mask[i] else COLORS['section_border'])
        )
        self.refresh_display()

    def shift(self, amount):
        if amount > 0:
            # rotate right by one
            self.pattern.insert(0, self.pattern.pop())
        else:
            # rotate left by one
            self.pattern.append(self.pattern.pop(0))
        self.refresh_display()



    def _on_toggle(self, r, c):
        if self.muted: return
        raw = r*32 + c - self.shift_offset
        idx = raw % 64
        if self.pattern[idx] == 'disabled': return

        # record undo
        self.sequencer.undo_stack.append((self, idx, self.pattern[idx]))

        # do the toggle
        self.pattern[idx] = 'on' if self.pattern[idx]=='off' else 'off'
        self.refresh_display()


    def _on_half(self, r, c):
        if self.muted: return
        raw = r*32 + c - self.shift_offset
        idx = raw % 64

        # record undo
        self.sequencer.undo_stack.append((self, idx, self.pattern[idx]))

        # cycle off→half→on→off
        self.pattern[idx] = {
            'off':  'half',
            'half': 'on',
            'on':   'off'
        }[self.pattern[idx]]
        self.refresh_display()

    def _on_disable(self, r, c):
        if self.muted: return
        raw = r*32 + c - self.shift_offset
        idx = raw % 64

        # record undo
        self.sequencer.undo_stack.append((self, idx, self.pattern[idx]))

        # flip disabled
        self.pattern[idx] = 'off' if self.pattern[idx]=='disabled' else 'disabled'
        self.refresh_display()

    def clear_track(self):
        self.pattern = ['off'] * 64
        self.refresh_display()

    def update_positions(self):
        pos = []
        for r in range(2):
            for c in range(32):
                idx = r*32 + c - self.shift_offset
                if 0 <= idx < 64 and self.pattern[idx] != 'disabled' and self.segment_mask[idx//16]:
                    color = COLORS[self.pattern[idx]] if self.pattern[idx] in ('on','half') else COLORS['off']
                    pos.append((r, c, color))
        self.sequence_positions = pos

    def get_midi_note(self):
        if self.sequencer.solo_inst and self is not self.sequencer.solo_inst:
            return None
        if self.muted:
            return None
        try:
            return int(self.note_var.get())
        except:
            return None

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            # gray everything out
            for r in range(2):
                for b in self.step_buttons[r]:
                    b.config(bg=COLORS['disabled'])
            self.name_label.config(fg=COLORS['red'])
            self.sequence_positions = []
        else:
            self.name_label.config(fg=COLORS['text'])
            self.refresh_display()

    def apply_every(self, n: int):
        self.update_positions()
        for idx, (r, c, _) in enumerate(self.sequence_positions):
            pat_idx = r*32 + c - self.shift_offset
            self.pattern[pat_idx] = 'on' if idx % n == 0 else 'off'
        self.refresh_display()



class DrumSequencer:
    def __init__(self, root):
        self.half_mode = True   # start in “half” (one‐row) mode
        self.undo_stack  = [] 
        self.root = root
        self.solo_inst = None
        root.title("drumding")
        root.configure(bg=COLORS['bg'])
        self.container = tk.Frame(root, bg=COLORS['bg'])
        self.container.pack(fill='both', expand=True)
        self.container.grid_columnconfigure(2, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.left  = tk.Frame(self.container, bg=COLORS['bg'])
        self.right = tk.Frame(self.container, bg=COLORS['bg'])
        self.left.grid(row=0, column=0, padx=10, sticky='nw')
        self.right.grid(row=0, column=1, padx=10, sticky='nw')

        # build rows
        self.instruments = []
        for i,name in enumerate(INSTRUMENTS):
            parent = self.left if i<8 else self.right
            inst = InstrumentRow(parent, name, self)
            inst.frame.pack(pady=4, anchor='w')
            self.instruments.append(inst)

        # MIDI out
        try:
            self.midi_out = mido.open_output(MIDI_PORT_NAME)
        except Exception as e:
            print("MIDI Port Error:", e)
            self.midi_out = None

        # transport + BPM
        control_bar = tk.Frame(self.left, bg=COLORS['bg'])
        control_bar.pack(fill='x', pady=(8,0))
        self.bpm_var = tk.IntVar(value=120)
        bpm_slider = tk.Scale(
            control_bar, from_=0, to=240, orient='horizontal',
            variable=self.bpm_var, bg=COLORS['bg'], fg=COLORS['text'],
            troughcolor=COLORS['section_border'], highlightthickness=0,
            showvalue=False, length=(TOTAL_W//2)
        )
        bpm_slider.pack(side='left', padx=(0,8))

        btn_cfg = dict(
            bg=COLORS['bg'],
            relief='flat',
            font=('Fixedsys', 14, 'bold'),
            width=3,
            height=1,
            highlightthickness=0,          # kill focus rectangle
            activebackground=COLORS['bg']  # stop the white flash
        )

        tk.Button(control_bar, text='▶', fg=COLORS['on'],
                  command=self.play_sequence, **btn_cfg).pack(side='left', padx=2)
        tk.Button(control_bar, text='■', fg=COLORS['text'],
                  command=self.stop_sequence, **btn_cfg).pack(side='left', padx=2)
        # half / full toggles
        self.half_btn = tk.Button(
            control_bar, text='half',
            fg=COLORS['blue'],
            command=self.set_half,
            **btn_cfg
        )
        self.half_btn.pack(side='left', padx=2)

        self.full_btn = tk.Button(
            control_bar, text='full',
            fg=COLORS['text'],
            command=self.set_full,
            **btn_cfg
        )
        self.full_btn.pack(side='left', padx=2)

        
        tk.Button(control_bar, text='💣', fg='red',
                  command=self.factory_reset, **btn_cfg).pack(side='left', padx=2)
                # start in half-mode with segments 3-4 off
        self.set_half()


        # state for timing
        self.running        = False
        self.next_time      = None
        self.delay          = None
        self.last_positions = [None]*len(self.instruments)
        self.step_counters  = [0]*len(self.instruments)

        # keybindings
        root.bind('<space>', lambda e: self.stop_sequence() if self.running else self.play_sequence())
        root.bind('s',      lambda e: self.stop_sequence())
        root.bind('r',      lambda e: self.record_sequence())
        root.bind('c',      lambda e: self.clear_pattern())

    def _solo(self, inst):
        # toggle solo on/off
        if self.solo_inst is inst:
            self.solo_inst = None
        else:
            self.solo_inst = inst
        # update label colors
        for row in self.instruments:
            if self.solo_inst and row is not self.solo_inst:
                row.name_label.config(fg=COLORS['section_border'])
            else:
                row.name_label.config(fg=COLORS['text'])

    def _do_tick(self):
        H = COLORS['highlight']
        for idx, inst in enumerate(self.instruments):
            # restore previous glow
            prev = self.last_positions[idx]
            if prev:
                pr,pc,orig = prev
                inst.step_buttons[pr][pc].config(bg=orig)

            note = inst.get_midi_note()
            if note is None:
                self.last_positions[idx] = None
                continue

            pos = inst.sequence_positions
            if not pos:
                self.last_positions[idx] = None
                continue

            i = self.step_counters[idx] % len(pos)
            r,c,orig_bg = pos[i]
            btn = inst.step_buttons[r][c]

            # glow
            btn.config(bg=H)
            self.last_positions[idx] = (r,c,orig_bg)
            fade_ms = int(self.delay*1000*0.8)
            self.root.after(fade_ms, lambda b=btn, col=orig_bg: b.config(bg=col))

            # send MIDI with full or half velocity
            if self.midi_out and orig_bg in (COLORS['on'], COLORS['half']):
                vel = 100 if orig_bg==COLORS['on'] else 50
                self.midi_out.send(mido.Message('note_on',  note=note, velocity=vel))
                self.midi_out.send(mido.Message('note_off', note=note, velocity=vel))

            self.step_counters[idx] += 1

    def _schedule_step(self):
        if not self.running:
            return
        now = time.perf_counter()
        while self.next_time <= now:
            self._do_tick()
            self.next_time += self.delay
        ms = max(int((self.next_time - now)*1000), 0)
        self.root.after(ms, self._schedule_step)

    def play_sequence(self):
        if self.running: return
        self.running   = True
        self.next_time = time.perf_counter()
        self.delay     = 60.0 / max(1,self.bpm_var.get()) / 4.0
        self._schedule_step()

    def stop_sequence(self):
        self.running = False
        for idx,prev in enumerate(self.last_positions):
            if prev:
                pr,pc,orig = prev
                self.instruments[idx].step_buttons[pr][pc].config(bg=orig)
        self.last_positions = [None]*len(self.instruments)
        if self.midi_out:
            for ch in range(16):
                self.midi_out.send(mido.Message('control_change', channel=ch, control=123, value=0))
        self.step_counters = [0]*len(self.instruments)

    def record_sequence(self):
        print("REC toggled")

    def clear_pattern(self):
        for inst in self.instruments:
            for row in inst.step_buttons:
                for b in row:
                    b.config(bg=COLORS['off'])
            inst.update_positions()
        print("Pattern cleared")

    def factory_reset(self):
        # Custom pop-up confirmation dialog
        def on_yes():
            # Reset each instrument's track
            for inst in self.instruments:
                inst.pattern = ['off'] * 64  # Reset the track for each instrument
            
            print("Factory reset complete")
            for inst in self.instruments:
                inst.refresh_display()  # Refresh display for each instrument
            popup.destroy()  # Close the custom popup

        def on_no():
            popup.destroy()  # Close the popup without doing anything

        # Create a custom pop-up window
        popup = tk.Toplevel(self.root)
        popup.title("drumding")
        popup.configure(bg=COLORS['bg'])  # Match the background color to your GUI
        popup.geometry('150x150')  # Set the size of the popup window

        # Message in the pop-up
        label = tk.Label(popup, text="you sure?", 
                         bg=COLORS['bg'], fg=COLORS['text'], font=('Fixedsys', 12))
        label.pack(pady=20)

        # Buttons for Yes and No
        yes_button = tk.Button(popup, text="yes", fg=COLORS['text'], bg=COLORS['blue'], 
                               command=on_yes, relief='flat', font=('Fixedsys', 12))
        yes_button.pack(side='left', padx=20, pady=10)
        
        no_button = tk.Button(popup, text="no", fg=COLORS['text'], bg=COLORS['blue'], 
                              command=on_no, relief='flat', font=('Fixedsys', 12))
        no_button.pack(side='right', padx=20, pady=10)

        popup.grab_set()  # Make the popup modal (user can't interact with the main window until it's closed)
        popup.transient(self.root)  # Make the popup window attached to the main window
        self.root.wait_window(popup)  # Wait for the popup to close


    def set_half(self):
        self.half_mode = True
        self.half_btn.config(fg=COLORS['blue'])
        self.full_btn.config(fg=COLORS['text'])
        for inst in self.instruments:
            hdr  = inst.header.winfo_reqheight()
            rowh = inst.row_frames[0].winfo_reqheight()
            inst.frame.config(height=hdr + rowh + 8)
            inst.refresh_display()

    def set_full(self):
        self.half_mode = False
        self.half_btn.config(fg=COLORS['text'])
        self.full_btn.config(fg=COLORS['blue'])
        for inst in self.instruments:
            # also enable all segments here if you like:
            inst.segment_mask = [True, True, True, True]
            for i, btn in enumerate(inst.seg_btns):
                btn.config(bg='#9D00FF')

            hdr  = inst.header.winfo_reqheight()
            rowh = inst.row_frames[0].winfo_reqheight()
            inst.frame.config(height=hdr + rowh*2 + 8)
            inst.refresh_display()
            
    def undo_last(self):
        if not self.undo_stack:
            return
        inst, idx, old = self.undo_stack.pop()
        inst.pattern[idx] = old
        inst.refresh_display()


        # ────────────────────────────────────────────────────────────────
    #   VIEW MODES
    # ────────────────────────────────────────────────────────────────
    def set_full(self):
        self.half_mode = False
        self.half_btn.config(fg=COLORS['text'])
        self.full_btn.config(fg=COLORS['blue'])
        
        for inst in self.instruments:
            # ─── enable all 4 segments ───────────────────
            inst.segment_mask = [True, True, True, True]
            for i, btn in enumerate(inst.seg_btns):
                btn.config(bg='#9D00FF')
            # ─── resize for two rows ──────────────────────
            hdr  = inst.header.winfo_reqheight()
            rowh = inst.row_frames[0].winfo_reqheight()
            inst.frame.config(height=hdr + rowh*2 + 8)
            inst.refresh_display()

    def set_full(self):
        """Show both 32-step rows; segments 3–4 become user-controllable."""
        self.half_mode = False
        self.half_btn.config(fg=COLORS['section_border'])   # gray-out “half”
        self.full_btn.config(fg=COLORS['blue'])

        for inst in self.instruments:
            # restore two-row height
            hdr  = inst.header.winfo_reqheight()
            rowh = inst.row_frames[0].winfo_reqheight()
            inst.frame.config(height=hdr + rowh*2 + 8)

            # unlock segments 3 & 4 (they keep their ON/OFF masks)
            for i in (2, 3):
                inst.seg_btns[i].config(
                    state='normal',
                    bg=('#9D00FF' if inst.segment_mask[i]
                        else COLORS['section_border'])
                )

            inst.refresh_display()

if __name__ == '__main__':
    root = tk.Tk()
    root.state('zoomed')
    root.withdraw()
    app = DrumSequencer(root)
    root.deiconify()
    root.mainloop()



