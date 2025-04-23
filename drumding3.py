import tkinter as tk
import mido
import threading
import time

# ── GLOBAL CONFIGURATION & PRE-MEASURE ───────────────────────────────
MAX_TOTAL_STEPS    = 64
MIDI_PORT_NAME     = 'gord 1'
INSTRUMENTS        = [
    "kick", "snare", "closed hat", "open hat",
    "tom 1", "tom 2", "ride ping", "ride wash",
    "china", "crash 1", "crash 2", "clamp",
    "aux", "aux", "aux", "aux"
]

COLORS = {
    'bg':              'black',
    'on':              '#00ff00',
    'off':             '#668866',
    'disabled':        '#111111',
    'section_border':  '#666666',
    'text':            'white',
    'highlight':       '#00cc00',
    'blue':            '#0165FC',
}

# Measure a single button width once, then destroy hidden root
_hidden_root = tk.Tk()
_hidden_root.withdraw()
_fb = tk.Frame(_hidden_root)
_sample = tk.Button(_fb, width=2, height=1, relief='flat')
_sample.pack()
_hidden_root.update_idletasks()
BTN_W       = _sample.winfo_reqwidth()
_hidden_root.destroy()
CELL_TOTAL  = BTN_W + 2
TOTAL_W     = CELL_TOTAL * 32

class InstrumentRow:
    def __init__(self, parent, name):
        self.name         = name
        self.sections     = 0
        self.step_buttons = [[], []]
        self.muted        = False
        self.muted_backup = []

        # Container frame fixed size
        self.frame = tk.Frame(
            parent, bg=COLORS['bg'],
            highlightbackground=COLORS['section_border'],
            highlightthickness=1,
            width=TOTAL_W + 12  # reserve width
        )
        self.frame.pack_propagate(False)

        # Header layout: name, count, –, +, note entry
        self.header = tk.Frame(self.frame, bg=COLORS['bg'])
        self.header.pack(fill='x', pady=2)
        tk.Label(
            self.header, text=name,
            bg=COLORS['bg'], fg=COLORS['text'],
            width=12, anchor='w'
        ).pack(side='left', padx=(8,0))

        self.label_btn = tk.Button(
            self.header, text="32/64",
            bg=COLORS['bg'], fg=COLORS['highlight'],
            relief='flat', command=self.toggle_mute
        )
        self.label_btn.pack(side='left', padx=4)

        # add tiny 1–16 buttons matching 32/64 style
        num_frame = tk.Frame(self.header, bg=COLORS['bg'])
        num_frame.pack(side='left', padx=(6,0))
        for i in range(1, 17):
            btn = tk.Button(
                num_frame,
                text=str(i),
                bg=COLORS['bg'], fg=COLORS['blue'],
                relief='flat'
            )
            btn.pack(side='left', padx=1)

        # spacer to push MIDI-entry and –/+ to the right
        spacer = tk.Frame(self.header, bg=COLORS['bg'])
        spacer.pack(side='left', fill='x', expand=True)

        # MINUS then PLUS so minus is always on left
        self.remove_btn = tk.Button(
            self.header, text='-', command=self.remove_section,
            width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['highlight'], relief='flat'
        )
        self.remove_btn.pack(side='left', padx=(2,0))

        self.extend_btn = tk.Button(
            self.header, text='+', command=self.extend_section,
            width=2, height=1,
            bg=COLORS['bg'], fg=COLORS['highlight'], relief='flat'
        )
        self.extend_btn.pack(side='right')

        self.note_var = tk.StringVar()
        tk.Entry(
            self.header, textvariable=self.note_var,
            width=4, bg='black', fg='white', justify='center'
        ).pack(side='right', padx=8)

        # Grid frame matching background
        self.grid_frame = tk.Frame(self.frame, bg=COLORS['bg'])
        self.grid_frame.pack(anchor='w', padx=6)

        # Two row containers
        self.row_frames = []
        for _ in range(2):
            rf = tk.Frame(self.grid_frame, bg=COLORS['bg'])
            rf.pack(anchor='w')
            self.row_frames.append(rf)

        # Build initial 32 steps (two sections)
        self.extend_section()
        self.extend_section()

        # Now that rows exist, measure header and row height
        self.frame.update_idletasks()
        header_h = self.header.winfo_reqheight()
        row_h    = self.row_frames[0].winfo_reqheight()
        total_h  = header_h + (row_h * 2) + 8

        # Fix container height
        self.frame.config(height=total_h)

    def get_midi_note(self):
        if self.muted:
            return None
        try:
            return int(self.note_var.get())
        except ValueError:
            return None

    def extend_section(self):
        if self.sections * 16 >= MAX_TOTAL_STEPS:
            return
        idx = self.sections
        r   = idx // 2
        off = (idx % 2) * 16
        for i in range(16):
            b = tk.Button(
                self.row_frames[r], width=2, height=1,
                bg=COLORS['off'], relief='flat'
            )
            b.grid(row=0, column=off+i, padx=1, pady=1)
            b.bind('<Button-1>', lambda e, rr=r, cc=off+i: self.toggle(rr, cc))
            b.bind('<Double-Button-1>', lambda e, rr=r, cc=off+i: self.disable(rr, cc))
            self.step_buttons[r].append(b)

        self.sections += 1
        self.label_btn.config(text=f"{self.sections*16}/{MAX_TOTAL_STEPS}")

    def remove_section(self):
        if self.sections == 0:
            return
        self.sections -= 1
        idx = self.sections
        r   = idx // 2
        for _ in range(16):
            if self.step_buttons[r]:
                btn = self.step_buttons[r].pop()
                btn.destroy()
        self.label_btn.config(text=f"{self.sections*16}/{MAX_TOTAL_STEPS}")

    def toggle(self, r, c):
        if self.muted:
            return
        if c < len(self.step_buttons[r]):
            b = self.step_buttons[r][c]
            # ignore disabled cells
            if b['bg'] == COLORS['disabled']:
                return
            new = COLORS['on'] if b['bg'] == COLORS['off'] else COLORS['off']
            b.config(bg=new)

    def disable(self, r, c):
        if self.muted:
            return
        if c < len(self.step_buttons[r]):
            b = self.step_buttons[r][c]
            # double-click toggles disabled state
            if b['bg'] == COLORS['disabled']:
                b.config(bg=COLORS['off'])
            else:
                b.config(bg=COLORS['disabled'])

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.muted_backup = [[b['bg'] for b in row] for row in self.step_buttons]
            for row in self.step_buttons:
                for b in row:
                    b.config(bg=COLORS['disabled'])
        else:
            for ri, row in enumerate(self.step_buttons):
                for ci, b in enumerate(row):
                    try:
                        b.config(bg=self.muted_backup[ri][ci])
                    except IndexError:
                        b.config(bg=COLORS['off'])

class DrumSequencer:
    def __init__(self, root):
        self.root = root
        self.root.title("Drumding")

        root.configure(bg=COLORS['bg'])
        self.container = tk.Frame(root, bg=COLORS['bg'])
        self.container.pack(fill='both', expand=True)
        self.container.grid_columnconfigure(2, weight=1)
        # allow row 0 to expand so ctrl_frame can grow vertically
        self.container.grid_rowconfigure(0, weight=1)

        

        self.left  = tk.Frame(self.container, bg=COLORS['bg'])
        self.right = tk.Frame(self.container, bg=COLORS['bg'])
        self.left.grid(row=0, column=0, padx=10, sticky='nw')
        self.right.grid(row=0, column=1, padx=10, sticky='nw')

        self.instruments = []
        for i, name in enumerate(INSTRUMENTS):
            parent = self.left if i < 8 else self.right
            inst   = InstrumentRow(parent, name)
            inst.frame.pack(pady=4, anchor='w')
            self.instruments.append(inst)

        try:
            self.midi_out = mido.open_output(MIDI_PORT_NAME)
        except Exception as e:
            print('MIDI Port Error:', e)
            self.midi_out = None
            
        # keep track of last highlighted pad per track
        self.last_positions = [None] * len(self.instruments)

                # ── BPM & Slave-Mode Controls ───────────────────
        self.bpm_var   = tk.IntVar(value=120)
        self.slave_var = tk.BooleanVar(value=False)
        ctrl_frame = tk.Frame(self.container, bg=COLORS['bg'])
        ctrl_frame.grid(row=0, column=2, padx=10, pady=(4,0), sticky='n')
        header_frame = tk.Frame(ctrl_frame, bg=COLORS['bg'])
        header_frame.pack(side='top', fill='x')
        
        bpm_slider = tk.Scale(
            ctrl_frame,
            from_=0, to=240, orient='horizontal',
            variable=self.bpm_var,
            bg=COLORS['bg'], fg=COLORS['text'],
            troughcolor=COLORS['section_border'],
            highlightthickness=0
        )
        bpm_slider.pack(in_=header_frame, side='left')

        self.bpm_entry = tk.Entry(
            ctrl_frame,
            textvariable=self.bpm_var,
            width=4, justify='center',
            bg=COLORS['bg'], fg=COLORS['text'],
            relief='flat'
        )
        self.bpm_entry.pack(in_=header_frame, side='left', padx=4)

        tk.Checkbutton(
            ctrl_frame,
            variable=self.slave_var,
            bg=COLORS['bg'],
            selectcolor='red',
            bd=0,
            relief='flat'
        ).pack(in_=header_frame, side='left', padx=8)
        self.transport_frame = tk.Frame(ctrl_frame, bg=COLORS['bg'])
        self.transport_frame.pack(side='bottom', fill='x', pady=(4,0))
        
        header_frame.update_idletasks()
        w = header_frame.winfo_reqwidth()
        ctrl_frame.config(width=w)
        # configure 2 columns and 2 rows
        for i in range(2):
            self.transport_frame.grid_columnconfigure(i, weight=1)
            self.transport_frame.grid_rowconfigure(i, weight=1)

        btn_cfg = dict(bg=COLORS['bg'], relief='flat', font=('Fixedsys', 14, 'bold'))

        # row 0: ▶ and ■
        tk.Button(self.transport_frame, text='▶', fg=COLORS['on'],
                  command=self.play_sequence, **btn_cfg
        ).grid(row=0, column=0, sticky='nsew')
        tk.Button(self.transport_frame, text='■', fg=COLORS['text'],
                  command=self.stop_sequence, **btn_cfg
        ).grid(row=0, column=1, sticky='nsew')

        # row 1: ● and ✖
        tk.Button(self.transport_frame, text='●', fg='red',
                  command=self.record_sequence, **btn_cfg
        ).grid(row=1, column=0, sticky='nsew')
        tk.Button(self.transport_frame, text='✖', fg=COLORS['text'],
                  command=self.clear_pattern, **btn_cfg
        ).grid(row=1, column=1, sticky='nsew')
        # ── Start sequencer ─────────────────────────────
        self.running = True
        threading.Thread(target=self.run_sequence, daemon=True).start()

    
    def run_sequence(self):
        global_step = 0
        HIGHLIGHT   = '#FDE8AC'

        while self.running:
            start = time.perf_counter()
            bpm   = self.bpm_var.get()
            delay = 60.0 / max(1, bpm) / 4.0

            for idx, inst in enumerate(self.instruments):
                # restore any previously highlighted pad
                prev = self.last_positions[idx]
                if prev:
                    pr, pc, orig_bg = prev
                    try:
                        inst.step_buttons[pr][pc].config(bg=orig_bg)
                    except Exception:
                        pass

                note   = inst.get_midi_note()
                length = inst.sections * 16
                if note is None or length == 0:
                    self.last_positions[idx] = None
                    continue

                # map the global_step into your 2×32 grid
                pos     = global_step % length
                segment = pos // 16
                r       = segment // 2
                offset  = (segment % 2) * 16
                c       = offset + (pos % 16)

                try:
                    btn = inst.step_buttons[r][c]
                except IndexError:
                    self.last_positions[idx] = None
                    continue

                orig_bg = btn['bg']
                btn.config(bg=HIGHLIGHT)
                self.last_positions[idx] = (r, c, orig_bg)

                if orig_bg == COLORS['on']:
                    self.midi_out.send(mido.Message('note_on',  note=note, velocity=100))
                    self.midi_out.send(mido.Message('note_off', note=note, velocity=100))

            # advance and pace the clock
            global_step += 1
            elapsed     = time.perf_counter() - start
            to_sleep    = delay - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)


    def play_sequence(self):
        if not self.running:
            # ← this line is indented 8 spaces (two levels)
            self.running = True
            threading.Thread(target=self.run_sequence, daemon=True).start()

    def stop_sequence(self):
        # stop the loop
        self.running = False

        # restore any highlighted pads
        for idx, prev in enumerate(self.last_positions):
            if prev:
                pr, pc, orig_bg = prev
                try:
                    self.instruments[idx].step_buttons[pr][pc].config(bg=orig_bg)
                except Exception:
                    pass
        # reset for next time
        self.last_positions = [None] * len(self.instruments)

        # existing “all notes off” logic
        if self.midi_out:
            for ch in range(16):
                msg = mido.Message('control_change', channel=ch, control=123, value=0)
                self.midi_out.send(msg)

    def record_sequence(self):
        print("REC toggled")

    def clear_pattern(self):
        for inst in self.instruments:
            for row in inst.step_buttons:
                for b in row:
                    b.config(bg=COLORS['off'])
        print("Pattern cleared")

if __name__ == '__main__':
    root = tk.Tk()
    root.state('zoomed')
    root.withdraw()
    app = DrumSequencer(root)
    root.deiconify()
    root.mainloop()





