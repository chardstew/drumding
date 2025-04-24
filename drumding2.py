import tkinter as tk
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
    'on':              '#00ff00',
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
    def __init__(self, parent, name):
        self.name         = name
        self.sections     = 0
        self.step_buttons = [[], []]
        self.muted        = False
        self.muted_backup = []
        self.sequence_positions = []

        # ── container ────────────────────────────────────────────────
        self.frame = tk.Frame(
            parent, bg=COLORS['bg'],
            highlightbackground=COLORS['section_border'],
            highlightthickness=1,
            width=TOTAL_W + 12
        )
        self.frame.pack_propagate(False)
        self.header = tk.Frame(self.frame, bg=COLORS['bg'])
        self.header.pack(fill='x', pady=2)

        # name label & count
        self.name_label = tk.Label(self.header, text=name,
             bg=COLORS['bg'], fg=COLORS['text'],
             width=12, anchor='w')
        self.name_label.pack(side='left', padx=(8,0))
        # Bind: double-click → mute; Ctrl-click → solo
        self.name_label.bind('<Double-Button-1>', lambda e, inst=self: inst.toggle_mute())
        self.name_label.bind('<Control-Button-1>',  lambda e, inst=self: self.sequencer._solo(inst))


        # “every” dropdown instead of 1–16 buttons
        every_btn = tk.Menubutton(
            self.header, text="every",
            bg=COLORS['bg'], fg=COLORS['blue'],
            relief='flat', direction='below'
        )
        menu = tk.Menu(every_btn, tearoff=0, bg=COLORS['bg'], fg=COLORS['text'])
        for n in range(1, 17):
            # when you choose n, build the pattern every n steps
            menu.add_command(
                label=str(n),
                command=lambda n=n: self.apply_every(n)
            )
        every_btn.configure(menu=menu)
        every_btn.pack(side='left', padx=(6,0))

        # spacer + note entry + – / +
        tk.Frame(self.header, bg=COLORS['bg']).pack(side='left', fill='x', expand=True)
        self.extend_btn = tk.Button(self.header, text='+', width=2, height=1,
                                    bg=COLORS['bg'], fg=COLORS['text'],
                                    relief='flat', command=self.extend_section)
        self.extend_btn.pack(side='right')
        self.remove_btn = tk.Button(self.header, text='-', width=2, height=1,
                                    bg=COLORS['bg'], fg=COLORS['text'],
                                    relief='flat', command=self.remove_section)
        self.remove_btn.pack(side='right', padx=(2,0))

        self.note_var = tk.StringVar()
        tk.Entry(self.header, textvariable=self.note_var,
                 width=4, bg='black', fg='white', justify='left'
        ).pack(side='right', padx=8)
        
        

        default = DEFAULT_NOTES.get(name)
        if default is not None:
            self.note_var.set(str(default))
            
        # ── per-track CLEAR button ────────────────────────
        self.clear_btn = tk.Button(
            self.header, text='💣',
            width=3, height=1,
            bg=COLORS['bg'], fg=COLORS['red'],
            relief='flat',
            command=self.clear_track
        )
        self.clear_btn.pack(side='right', padx=(2,0))


        # ── grid of 64 hidden buttons ───────────────────────────────
        self.grid_frame = tk.Frame(self.frame, bg=COLORS['bg'])
        self.grid_frame.pack(anchor='w', padx=6)
        self.row_frames = [tk.Frame(self.grid_frame, bg=COLORS['bg']) for _ in range(2)]
        for rf in self.row_frames:
            rf.pack(anchor='w')

        for idx in range(4):
            r   = idx // 2
            off = (idx % 2)*16
            for i in range(16):
                b = tk.Button(
                    self.row_frames[r], width=2, height=1,
                    bg=COLORS['off'], relief='flat'
                )
                b.grid(row=0, column=off+i, padx=1, pady=1)
                b.bind('<Button-1>',        lambda e, rr=r, cc=off+i: self._on_toggle(rr,cc))
                b.bind('<Double-Button-1>', lambda e, rr=r, cc=off+i: self._on_disable(rr,cc))
                self.step_buttons[r].append(b)
        for row in self.step_buttons:
            for b in row:
                b.grid_remove()

        # show first 32 steps
        self.extend_section()
        self.extend_section()

        # fix height
        self.frame.update_idletasks()
        header_h = self.header.winfo_reqheight()
        row_h    = self.row_frames[0].winfo_reqheight()
        self.frame.config(height=header_h + row_h*2 + 8)

    def clear_track(self):
        # Clear all ON-green and re-enable any disabled pads in this row."""
        for row in self.step_buttons:
            for b in row:
            # reset _every_ pad to OFF, regardless of disabled state
                b.config(bg=COLORS['off'])
        self.update_positions()

    


    def get_midi_note(self):
        if self.muted: return None
        try: return int(self.note_var.get())
        except: return None

    def update_positions(self):
        pos = []
        for r,row in enumerate(self.step_buttons):
            for c,b in enumerate(row):
                if b.winfo_ismapped() and b['bg'] != COLORS['disabled']:
                    pos.append((r,c,b['bg']))
        self.sequence_positions = pos

    def extend_section(self):
        if self.sections*16 >= MAX_TOTAL_STEPS: return
        idx = self.sections
        r   = idx//2
        off = (idx%2)*16
        for i in range(16):
            self.step_buttons[r][off+i].grid()
        self.sections += 1
        self.label_btn.config(text=f"{self.sections*16}/{MAX_TOTAL_STEPS}")
        self.update_positions()

    def remove_section(self):
        if self.sections == 0: return
        idx = self.sections - 1
        r   = idx//2
        off = (idx%2)*16
        for i in range(16):
            self.step_buttons[r][off+i].grid_remove()
        self.sections -= 1
        self.label_btn.config(text=f"{self.sections*16}/{MAX_TOTAL_STEPS}")
        self.update_positions()

    def _on_toggle(self, r, c):
        if self.muted: return
        b = self.step_buttons[r][c]
        if b['bg'] == COLORS['disabled']: return
        b.config(bg = COLORS['on'] if b['bg']==COLORS['off'] else COLORS['off'])
        self.update_positions()

    def _on_disable(self, r, c):
        if self.muted: return
        b = self.step_buttons[r][c]
        b.config(bg = COLORS['off'] if b['bg']==COLORS['disabled'] else COLORS['disabled'])
        self.update_positions()

    def toggle_mute(self):
        # flip the flag
        self.muted = not self.muted

        # update label color (red when muted, white when unmuted)
        self.name_label.config(
            fg = COLORS['red'] if self.muted else COLORS['text']
        )

        # refresh solo/mute UI in case a solo is active
        self.sequencer._solo(self.sequencer.solo_inst)
        
        else:
                for ri,row in enumerate(self.step_buttons):
                for ci,b in enumerate(row):
                    try:
                        b.config(bg=self.muted_backup[ri][ci])
                        except:
                            b.config(bg=COLORS['off'])
    def apply_every(self, n: int):
        # Turn on every nᵗʰ *visible* pad (step 1, 1+n, 1+2n, …)
        # 1) Refresh our cache of exactly which pads are mapped & enabled:
        self.update_positions()

        # 2) Walk that list in order, turning step 1, 1+n, 1+2n… ON, the rest OFF.
        for idx, (r, c, orig_bg) in enumerate(self.sequence_positions):
            b = self.step_buttons[r][c]
            # idx % n == 0 ⇒ this is step 1, 1+n, 1+2n, …
            if idx % n == 0:
                b.config(bg=COLORS['on'])
            else:
                b.config(bg=COLORS['off'])

        # 3) Re-cache, so your sequencer thread sees the new pattern immediately:
        self.update_positions()

class DrumSequencer:
    def __init__(self, root):
        self.sequencer = sequencer
        self.root = root
        root.title("Drumding")
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
            inst = InstrumentRow(parent, name, sequencer=self)
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

        btn_cfg = dict(bg=COLORS['bg'], relief='flat',
                       font=('Fixedsys',14,'bold'), width=3, height=1)
        tk.Button(control_bar, text='▶', fg=COLORS['on'],
                  command=self.play_sequence, **btn_cfg).pack(side='left', padx=2)
        tk.Button(control_bar, text='■', fg=COLORS['text'],
                  command=self.stop_sequence, **btn_cfg).pack(side='left', padx=2)
        tk.Button(control_bar, text='●', fg='red',
                  command=self.record_sequence, **btn_cfg).pack(side='left', padx=2)
        tk.Button(control_bar, text='✖', fg=COLORS['text'],
                  command=self.clear_pattern, **btn_cfg).pack(side='left', padx=2)
        tk.Button(control_bar, text='💣', fg='red',
                  command=self.factory_reset, **btn_cfg).pack(side='left', padx=2)


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

    def _do_tick(self):
        H = COLORS['highlight']
        for idx, inst in enumerate(self.instruments):

            # ── SOLO FILTER ─────────────────────────────────────
            if self.solo_inst is not None and inst is not self.solo_inst:
                # advance its counter so patterns stay in sync
                self.step_counters[idx] += 1
                # clear any glow left behind
                self.last_positions[idx] = None
                continue

            # restore previous glow
            prev = self.last_positions[idx]
            if prev:
                pr,pc,orig = prev
                inst.step_buttons[pr][pc].config(bg=orig)

            note = inst.get_midi_note()
            if note is None:
                self.last_positions[idx] = None
                continue

            # glow
            btn.config(bg=H)
            self.last_positions[idx] = (r,c,orig_bg)
            fade_ms = int(self.delay*1000*0.8)
            self.root.after(fade_ms, lambda b=btn, col=orig_bg: b.config(bg=col))

            # send MIDI if it was “on”
            if orig_bg == COLORS['on'] and self.midi_out:
                self.midi_out.send(mido.Message('note_on',  note=note, velocity=100))
                self.midi_out.send(mido.Message('note_off', note=note, velocity=100))

            self.step_counters[idx] += 1

    def _schedule_step(self):
        if not self.running:
            return
        now = time.perf_counter()
        # catch up on any missed ticks
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
        # clear glows
        for idx,prev in enumerate(self.last_positions):
            if prev:
                pr,pc,orig = prev
                self.instruments[idx].step_buttons[pr][pc].config(bg=orig)
        self.last_positions = [None]*len(self.instruments)
        # all-notes-off
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
        # Wipe every track’s pattern AND restore its default note."""
        for inst in self.instruments:
            inst.clear_track()   # clear ON/disabled pads
            default = DEFAULT_NOTES.get(inst.name)
            inst.note_var.set(str(default) if default is not None else "")
        print("Factory defaults restored")

    def _solo(self, inst):
        # toggle solo state
        if self.solo_inst is inst:
            self.solo_inst = None
        else:
            self.solo_inst = inst

        # update every track’s label color
        for other in self.instruments:
            if other.muted:
                fg = COLORS['red']
            elif self.solo_inst is None:
                fg = COLORS['text']
            elif other is self.solo_inst:
                fg = COLORS['text']
            else:
                fg = COLORS['disabled']
            other.name_label.config(fg=fg)


if __name__ == '__main__':
    root = tk.Tk()
    root.state('zoomed')
    root.withdraw()
    app = DrumSequencer(root)
    root.deiconify()
    root.mainloop()
