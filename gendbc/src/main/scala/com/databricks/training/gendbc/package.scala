package com.databricks.training

/** This package contains a tool to generate DBC files from source notebooks.
  *
  * It's fragile: If the format of the exported source notebooks changes, or
  * if the format of the DBC JSON changes, this tool will break.
  */
package object gendbc
