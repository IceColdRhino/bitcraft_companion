import customtkinter as ctk
import logging
import numpy as np
from tkinter import ttk


class JobPopup(ctk.CTkToplevel):
    """A detailed popup window for seeing more info on a specific job."""

    def __init__(self, parent, cell, job_data,):# current_selection, callback, custom_key=None):
        super().__init__(parent)

        self.title(job_data["job"])
        self.geometry("350x500")

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
            "Item": 100,
            "Rarity": 100,
            "Quantity": 100,
            "Price Window": 100,
            "Sale Price": 100,
            "Job Value": 100,
        }

        self._create_widgets(job_data)

    def _create_widgets(self,job_data):
        style = ttk.Style()
        style.theme_use("default")

        # Configure the Treeview colors
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            fieldbackground="#343638",
            borderwidth=0,
            rowheight=28,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1f6aa5")])

        # Configure headers
        style.configure(
            "Treeview.Heading",
            background="#1e2124",
            foreground="#e0e0e0",
            font=("Segoe UI", 11, "normal"),
            padding=(8, 6),
            relief="flat",
            borderwidth=0,
        )
        style.map("Treeview.Heading", background=[("active", "#2c5d8f")])

        # textbox = ctk.CTkTextbox(self)
        # textbox.grid(row=0, column=0)
        # text_str = ""
        # for key in list(job_data.keys()):
        #     text_str += f"{key}: {job_data[key]}\n"
        # textbox.insert("0.0",text_str)

        self.input_label = ctk.CTkLabel(self,text=f"{job_data["long_name"]}")
        self.input_label.grid(row=0,column=0,columnspan=5)

        self.input_label = ctk.CTkLabel(self,text=f"Total Effort:\n{np.round(job_data["effort"],2)}")
        self.input_label.grid(row=1,column=0,sticky="w")

        self.input_label = ctk.CTkLabel(self,text=f"Total Time:\n{np.round(job_data["time"],2)}")
        self.input_label.grid(row=1,column=2,sticky="w")

        self.input_label = ctk.CTkLabel(self,text=f"Total Stamina:\n{np.round(job_data["stamina"],2)}")
        self.input_label.grid(row=1,column=4,sticky="w")

        self.output_label = ctk.CTkLabel(self,text=" ")
        self.output_label.grid(row=2,column=0,columnspan=5)

        self.input_label = ctk.CTkLabel(self,text=f"Expected Profit:\n{np.round(job_data["profit"],2)}")
        self.input_label.grid(row=4,column=1,sticky="w")

        self.input_label = ctk.CTkLabel(self,text=f"Profit per Minute:\n{np.round(job_data["profit"],2)}")
        self.input_label.grid(row=4,column=3,sticky="w")

        self.output_label = ctk.CTkLabel(self,text=" ")
        self.output_label.grid(row=5,column=0,columnspan=5)

        self.input_label = ctk.CTkLabel(self,text="Inputs")
        self.input_label.grid(row=6,column=0,columnspan=2,sticky="w")

        self.input_label = ctk.CTkLabel(self,text=f"Expected Cost: {np.round(job_data["cost"],2)}")
        self.input_label.grid(row=6,column=2,columnspan=3,sticky="w")

        self.input_tree = ttk.Treeview(self,columns=self.table_headers,show="tree headings")
        self.input_tree.grid(row=7,column=0,rowspan=1,columnspan=5,sticky="nesw")
        for header in self.table_headers:
            self.input_tree.heading(header, text=header, anchor="w")
            self.input_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.input_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.input_tree.heading("#0", text="", anchor="w")
        for entry in job_data["inputs"]:
            self.input_tree.insert("","end", values=entry)

        self.output_label = ctk.CTkLabel(self,text=" ")
        self.output_label.grid(row=10,column=0,columnspan=5)

        self.output_label = ctk.CTkLabel(self,text="Outputs")
        self.output_label.grid(row=11,column=0,columnspan=2,sticky="w")

        self.output_label = ctk.CTkLabel(self,text=f"Expected Gross: {np.round(job_data["gross"],2)}")
        self.output_label.grid(row=11,column=2,columnspan=3,sticky="w")

        self.output_tree = ttk.Treeview(self,columns=self.table_headers,show="tree headings")
        self.output_tree.grid(row=12,column=0,rowspan=1,columnspan=5,sticky="nesw")
        for header in self.table_headers:
            self.output_tree.heading(header, text=header, anchor="w")
            self.output_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.output_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.output_tree.heading("#0", text="", anchor="w")
        for entry in job_data["outputs"]:
            self.output_tree.insert("","end", values=entry)

        self.grid_rowconfigure((0,1,2,3,4,5,6,10,11),weight=1)
        self.grid_rowconfigure((7,8,9,12,13,14),weight=1)
        self.grid_columnconfigure((0,1,2,3,4), weight=1)