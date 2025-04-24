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
        self.sequencer   = sequencer
        self.name        = name
        self.sections    = 0
        self.step_buttons = [[], []]
        self.muted       = False
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

        # name label
        self.name_label = tk.Label(
            self.header, text=name,
            bg=COLORS['bg'], fg=COLORS['text'],
            width=12, anchor='w'
        )
        self.name_label.pack(side='left', padx=(8,0))
        # binds: double-click to mute, ctrl-click to solo
        self.name_label.bind('<Double-Button-1>', lambda e: self.toggle_mute())
        self.name_label.bind('<Control-Button-1>', lambda e: self.sequencer._solo(self))

        # count label
        self.label_btn = tk.Button(
            self.header, text="0/64",
            bg=COLORS['bg'], fg=COLORS['text'],
            relief='flat', state='disabled'
        )
        self.label_btn.pack(side='left', padx=4)

        # “every” dropdown
        every_btn = tk.Menubutton(
            self.header, text="every",
            bg=COLORS['bg'], fg=COLORS['blue'],
            relief='flat', direction='below'
        )
        menu = tk.Menu(every_btn, tearoff=0, bg=COLORS['bg'], fg=COLORS['text'])
        for n in range(1, 17):
            menu.add_command(
                label=str(n),
                command=lambda n=n: self.apply_every(n)
            )
        every_btn.configure(menu=menu)
        every_btn.pack(side='left', padx=(6,0))

        # spacer + note entry + – / +
        tk.Frame(self.header, bg=COLORS['bg']).pack(side='left', fill='x', expand=True)
        self.extend_btn = tk.Button(
            self.header, text='+', width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['text'],
            relief='flat', command=self.extend_section
        )
        self.extend_btn.pack(side='right')
        self.remove_btn = tk.Button(
            self.header, text='-', width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['text'],
            relief='flat', command=self.remove_section
        )
        self.remove_btn.pack(side='right', padx=(2,0))

        self.note_var = tk.StringVar()
        tk.Entry(
            self.header, textvariable=self.note_var,
            width=4, bg='black', fg='white', justify='left'
        ).pack(side='right', padx=8)

        default = DEFAULT_NOTES.get(name)
        if default is not None:
            self.note_var.set(str(default))

        # per-track CLEAR button (bomb)
        self.clear_btn = tk.Button(
            self.header, text='💣',
            width=3, height=1,
            bg=COLORS['bg'], fg=COLORS['red'],
            relief='flat', command=self.clear_track
        )
        self.clear_btn.pack(side='right', padx=(2,0))

        # grid of 64 hidden buttons
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
                # full-level toggle on normal click (ignore ctrl)
                b.bind(
                    '<Button-1>', 
                    lambda e, rr=r, cc=off+i: None if (e.state & 0x4) else self._on_toggle(rr,cc)
                )
                # half-level on ctrl-click
                b.bind(
                    '<Control-Button-1>', 
                    lambda e, rr=r, cc=off+i: self._on_half(rr,cc)
                )
                # disable on double-click
                b.bind(
                    '<Double-Button-1>', 
                    lambda e, rr=r, cc=off+i: self._on_disable(rr,cc)
                )
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

    def _on_toggle(self, r, c):
        if self.muted: return
        b = self.step_buttons[r][c]
        if b['bg'] == COLORS['disabled']: return
        new = COLORS['on'] if b['bg']==COLORS['off'] else COLORS['off']
        b.config(bg=new)
        self.update_positions()

    def _on_half(self, r, c):
        if self.muted: return
        b = self.step_buttons[r][c]
        cur = b['bg']
        if cur == COLORS['off']:
            b.config(bg=COLORS['half'])
        elif cur == COLORS['half']:
            b.config(bg=COLORS['on'])
        else:
            b.config(bg=COLORS['off'])
        self.update_positions()

    def _on_disable(self, r, c):
        if self.muted: return
        b = self.step_buttons[r][c]
        new = COLORS['off'] if b['bg']==COLORS['disabled'] else COLORS['disabled']
        b.config(bg=new)
        self.update_positions()

    def clear_track(self):
        # reset every pad to OFF
        for row in self.step_buttons:
            for b in row:
                b.config(bg=COLORS['off'])
        self.update_positions()

    def get_midi_note(self):
        # enforce solo
        if self.sequencer.solo_inst and self is not self.sequencer.solo_inst:
            return None
        if self.muted:
            return None
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

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.muted_backup = [[b['bg'] for b in row] for row in self.step_buttons]
            for row in self.step_buttons:
                for b in row:
                    b.config(bg=COLORS['disabled'])
            self.name_label.config(fg=COLORS['red'])
        else:
            for ri,row in enumerate(self.step_buttons):
                for ci,b in enumerate(row):
                    try:
                        b.config(bg=self.muted_backup[ri][ci])
                    except:
                        b.config(bg=COLORS['off'])
            self.name_label.config(fg=COLORS['text'])
        self.update_positions()

    def apply_every(self, n: int):
        self.update_positions()
        for idx, (r, c, orig_bg) in enumerate(self.sequence_positions):
            b = self.step_buttons[r][c]
            b.config(bg=COLORS['on'] if idx % n == 0 else COLORS['off'])
        self.update_positions()

class DrumSequencer:
    def __init__(self, root):
        self.root = root
        self.solo_inst = None
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
        for inst in self.instruments:
            inst.clear_track()
            default = DEFAULT_NOTES.get(inst.name)
            inst.note_var.set(str(default) if default is not None else "")
        print("Factory defaults restored")

if __name__ == '__main__':
    root = tk.Tk()
    root.state('zoomed')
    root.withdraw()
    app = DrumSequencer(root)
    root.deiconify()
    root.mainloop()
