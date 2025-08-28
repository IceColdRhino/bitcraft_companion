import customtkinter as ctk
import logging
import numpy as np
from tkinter import ttk

from app.ui.styles import TreeviewStyles


class JobPopup(ctk.CTkToplevel):
    """A detailed popup window for seeing more info on a specific job."""

    def __init__(self, parent, cell, job_data,):# current_selection, callback, custom_key=None):
        super().__init__(parent)

        self.title(job_data["job"])
        self.geometry("600x500")

        # Make window resizable
        self.resizable(True, True)

        self.table_headers = ["Item",
                              "Rarity",
                              "Quantity",
                              "Price Window",
                              "Sale Price",
                              "Job Value",
                              ]
        self.column_widths = {
            "Item": 150,
            "Rarity": 100,
            "Quantity": 50,
            "Price Window": 100,
            "Sale Price": 50,
            "Job Value": 50,
        }

        self._create_widgets(job_data)

    def _create_widgets(self,job_data):
        # TODO: Make formatting more responsive to window size
        # Currently, the input/output frames have a fixed height,
        # and the summary frame adjusts its height with a window resize.
        # I would prefer the opposite - fixed summary and flexible input/output
        # but I could not figure out how to do that,

        # TODO: Make table scrollbars
        # While scrolling does function on the input/output tables,
        # I'd like to have a scrollbar to better indicate to the user that there's scrollable content.
        # However, every time I tried to place it, it appeared in strange place.

        # I suspect these two issues are related, and that I haven't properly
        # understood tkinter pack/grid methods and the manner they interact with frames.

        style = ttk.Style()

        # Apply centralized styling
        TreeviewStyles.apply_treeview_style(style)

        # Create the summary frame
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.grid(row=0,column=0,sticky="nsew",padx=20,pady=10)
        self._create_summary_section(self.summary_frame,job_data)

        # Create the input frame
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=1,column=0,sticky="nsew")
        self._create_input_section(self.input_frame,job_data)

        # Create the output frame
        self.output_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.output_frame.grid(row=2,column=0,sticky="nsew")
        self._create_output_section(self.output_frame,job_data)

        self.grid_rowconfigure(0,weight=1)
        self.grid_columnconfigure(0,weight=1)

    def _create_summary_section(self,parent,job_data):
        self.long_name = ctk.CTkLabel(
            parent,
            text=f"{job_data['long_name']}",
            font=ctk.CTkFont(size=14,weight="bold")
        )
        self.long_name.grid(row=0,column=0,rowspan=2,columnspan=5,sticky="nsew",padx=1,pady=1)

        self.effort = ctk.CTkLabel(
            parent,
            text=f"Total Effort:\n{np.round(job_data["effort"],2):,}",
        )
        self.effort.grid(row=2,column=0,sticky="nsew",padx=1,pady=1)

        self.time = ctk.CTkLabel(
            parent,
            text=f"Total Time [s]:\n{np.round(job_data["time"],2):,}",
        )
        self.time.grid(row=2,column=2,sticky="nsew",padx=1,pady=1)

        self.stamina = ctk.CTkLabel(
            parent,
            text=f"Total Stamina:\n{np.round(job_data["stamina"],2):,}",
        )
        self.stamina.grid(row=2,column=4,sticky="nsew",padx=1,pady=1)

        self.power = ctk.CTkLabel(
            parent,
            text=f"Power:\n{np.round(job_data["total_power"],2)}",
        )
        self.power.grid(row=3,column=1,sticky="nsew",padx=1,pady=1)

        self.speed = ctk.CTkLabel(
            parent,
            text=f"Speed:\n{np.round(job_data["swing_speed"],3)}",
        )
        self.speed.grid(row=3,column=3,sticky="nsew",padx=1,pady=1)

        self.profit = ctk.CTkLabel(
            parent,
            text=f"Expected Profit:\n{np.round(job_data["profit"],2):,}",
        )
        self.profit.grid(row=4,column=1,sticky="nsew",padx=1,pady=1)

        self.profit_rate = ctk.CTkLabel(
            parent,
            text=f"Expected Profit/min:\n{np.round(job_data["profit_per_min"],2):,}",
        )
        self.profit_rate.grid(row=4,column=3,sticky="nsew",padx=1,pady=1)

        parent.grid_rowconfigure((0,1,2,3,4), weight=1)
        parent.grid_columnconfigure((0,1,2,3,4,5), weight=1)
    
    def _create_input_section(self,parent,job_data):
        self.input_header = ctk.CTkFrame(parent, fg_color="transparent")
        self.input_header.pack(fill="x", padx=20, pady=1)

        self.input_label = ctk.CTkLabel(
            self.input_header,
            text="Inputs"
            )
        self.input_label.pack(side="left")

        self.input_cost = ctk.CTkLabel(
            self.input_header,
            text=f"Expected Cost: {np.round(job_data["cost"],2):,}"
            )
        self.input_cost.pack(side="right")

        self.input_tree = ttk.Treeview(
            parent,
            columns=self.table_headers,
            show="tree headings",
            style="Treeview",
            height=5,
            )

        for header in self.table_headers:
            self.input_tree.heading(header, text=header, anchor="w")
            self.input_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.input_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.input_tree.heading("#0", text="", anchor="w")
        for entry in job_data["inputs"]:
            self.input_tree.insert("","end", values=entry)
        
        self.input_tree.pack(fill="x", expand=True, padx=1, pady=1)

    def _create_output_section(self,parent,job_data):
        self.output_header = ctk.CTkFrame(parent, fg_color="transparent")
        self.output_header.pack(fill="x", padx=20, pady=1)

        self.output_label = ctk.CTkLabel(
            self.output_header,
            text="Outputs"
            )
        self.output_label.pack(side="left")

        self.output_cost = ctk.CTkLabel(
            self.output_header,
            text=f"Expected Gross: {np.round(job_data["gross"],2):,}"
            )
        self.output_cost.pack(side="right")

        self.output_tree = ttk.Treeview(
            parent,
            columns=self.table_headers,
            show="tree headings",
            style="Treeview",
            height=5,
            )

        for header in self.table_headers:
            self.output_tree.heading(header, text=header, anchor="w")
            self.output_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.output_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.output_tree.heading("#0", text="", anchor="w")
        for entry in job_data["outputs"]:
            self.output_tree.insert("","end", values=entry)

        self.output_tree.pack(fill="x", expand=True, padx=1, pady=1)