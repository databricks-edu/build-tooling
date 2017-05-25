package com.databricks.training.gendbc

import grizzled.file.Implicits.GrizzledFile
import java.io.File
import java.util.UUID

import spray.json._

import scala.annotation.tailrec
import scala.io.Source
import scala.util.{Failure, Success, Try}

/** The in-memory, parsed representation of a notebook cell.
  *
  * @param command   the notebook command
  * @param guid      the unique generated ID for the cell
  * @param position  the cell's position, relative to the other cells in the
  *                  containing notebook.
  */
case class NotebookCell(command: String,
                        guid:    UUID,
                        position: Int)

/** The in-memory representation of a notebook.
  *
  * @param name           the name of the notebook, derived from the file name
  * @param dbcOutputFile  the (base) output file name for the notebook (i.e.,
  *                       where the notebook will end up in the DBC file) which
  *                       is derived from the input file name. This is a
  *                       relative file name. It may have directory information,
  *                       but cannot be absolute.
  * @param language       the notebook language
  * @param guid           a globally unique ID (a UUID) for the notebook
  * @param cells          The individual notebook cells, in the order they were
  *                       read.
  */
case class Notebook (name:          String,
                     dbcOutputFile: File,
                     language:      String,
                     guid:          UUID,
                     cells:         Vector[NotebookCell]) {
  require(! dbcOutputFile.isAbsolute)

  import json.NotebookJsonProtocol._

  /** Convert this notebook to DBC JSON
    *
    * @return  the JSON AST
    */
  def toJSON: JsValue = this.toJson
}

/** Constructors and utility functions for the `Notebook` class. This is a
  * lower-level object. The preferred entry point is within the `Notebooks`
  * object.
  */
object Notebook {
  private case class NotebookMetadata(name:          String,
                                      zipOutputFile: File,
                                      language:      String,
                                      commentString: String)

  /** Parse a notebook from an exported notebook source file.
    *
    * @param file            the source file
    * @param dbcFolder       the top-level DBC folder, used to determine the
    *                        output file within the DBC. `None` means that the
    *                        folder should be derived from the file.
    * @param encoding        the encoding to use when reading the notebooks
    * @param trimLeadingPath the leading path to trim from the file
    *                        when constructing the output path
    *
    * @return the notebook, in a `Success`, or a `Failure` containing the
    *         error
    */
  def parse(file:            File,
            dbcFolder:       Option[String],
            encoding:        String,
            trimLeadingPath: String):
    Try[Notebook] = {

    for { metadata <- getNotebookMetadata(file, dbcFolder, trimLeadingPath)
          cells    <- parseNotebook(metadata.commentString, file, encoding) }
    yield Notebook(name          = metadata.name,
                   dbcOutputFile = metadata.zipOutputFile,
                   language      = metadata.language,
                   guid          = UUID.randomUUID,
                   cells         = cells)
  }

  // -------------------------------------------------------------------------
  // Private functions
  // -------------------------------------------------------------------------

  /** Get some metadata from the notebook file being parsed.
    *
    * @param file            the notebook file
    * @param dbcFolder       the top-level DBC folder, used to determine the
    *                        output file within the DBC. `None` means that the
    *                        folder should be derived from the file.
    * @param trimLeadingPath the leading path to trim from the file
    *                        when constructing the output path
    *
    * @return A `Success` with the metadata, or a `Failure` with any errors.
    */
  private def getNotebookMetadata(file:            File,
                                  dbcFolder:       Option[String],
                                  trimLeadingPath: String):
    Try[NotebookMetadata] = {

    // Push through File, to normalize the path (e.g., to remove extra "/")
    val toTrim = new File(trimLeadingPath).getPath

    // Figure out the notebook's output path within the DBC file.
    def dbcOutputPath(parent: File, base: String, ext: String): File = {
      import grizzled.file.util.joinPath
      val parentPath = parent.getAbsolutePath
      // Strip the leading path from the output path to get the relative path
      // for the file within the DBC zip file.
      val subdir = if (parentPath startsWith toTrim)
        parentPath.drop(toTrim.length)
      else
        parent.getPath

      val cleanedSubdir = if (subdir startsWith "/") subdir.drop(1) else subdir

      val folder = dbcFolder.getOrElse {
        // Use the last path component of the common prefix.
        file.getPath.split("/").find(_.nonEmpty).getOrElse("")
      }

      val path = joinPath(folder, cleanedSubdir)
      new File(joinPath(path, s"$base$ext"))
    }

    file.dirnameBasenameExtension match {
      case (d, b, e @ ".scala") =>
        Success(NotebookMetadata(name          = b,
                                 zipOutputFile = dbcOutputPath(d, b, e),
                                 language      = "scala",
                                 commentString = "//"))
      case (d, b, ".py") =>
        Success(NotebookMetadata(name          = b,
                                 zipOutputFile = dbcOutputPath(d, b, ".python"),
                                 language      = "python",
                                 commentString = "#"))
      case (d, b, e @ ".r") =>
        Success(NotebookMetadata(name          = b,
                                 zipOutputFile = dbcOutputPath(d, b, e),
                                 language      = "r",
                                 commentString = "#"))
      case (d, b, e @ ".sql") =>
        Success(NotebookMetadata(name          = b,
                                 zipOutputFile = dbcOutputPath(d, b, e),
                                 language      = "sql",
                                 commentString = "--"))
      case (_, _, ext) =>
        Failure(
          new Exception(s"File ${file.getPath}: Unknown file extension: $ext")
        )
      }
    }


  /** Parse a notebook from a file.
    *
    * @param commentString  The comment string prefix for the file's language
    * @param file           The file from which to read
    * @param encoding       The encoding with which to open the file
    *
    * @return A `Success` containing the parsed notebook cells, or a
    *         `Failure` with the error(s) that occurred.
    */
  private def parseNotebook(commentString: String,
                            file:          File,
                            encoding:      String):
    Try[Vector[NotebookCell]] = {

    // Regular expressions to aid in parsing various magic comments.
    val LeadingComment = """^\s*""" + commentString

    // Matches the Databricks header line at the beginning of a source-exported
    // notebook. All source-exported notebooks will have this line. We reject
    // any file that does not.
    val Header = (LeadingComment + """\s+Databricks\s+notebook.*$""").r

    // Matches a "MAGIC" comment, used for special cells. The first line of
    // a special cells starts with a "%" escape (%python, %scala, %sql, %md)
    // and might be followed by multiple lines. Each line will begin with
    // the special "MAGIC" token, followed by a single white space character
    // delimiter, followed by the content of the line (which, itself, might
    // start with white space--think Python).
    //
    // When parsing such a line, we need to keep everything after the
    // "MAGIC ". The following regular expression also handles the degenerate
    // case where "MAGIC" is alone on a line by itself, without any subsequent
    // white space at all, though that never seems to happen.
    val Magic = (LeadingComment + """\s+MAGIC\s?(.*)$""").r

    // Matches a "COMMAND" comment, which indicates the start of a new cell.
    val NewCell = (LeadingComment + """\s+COMMAND\s+-+.*$""").r

    @tailrec def parseNext(linesIn: List[String],
                           curCell: Vector[String],
                           cellNum: Int,
                           cells:   Vector[NotebookCell]):
      Vector[NotebookCell] = {

      def makeCell(cellLines: Vector[String], position: Int) = {
        // Strip leading and trailing empties.
        val cellContents = curCell.dropWhile(_.trim.isEmpty)
                                  .reverse
                                  .dropWhile(_.trim.isEmpty)
                                  .reverse

        NotebookCell(command  = cellContents.mkString("\n"),
                     guid     = UUID.randomUUID,
                     position = position)
      }

      linesIn match {
        case Nil if curCell.isEmpty =>
          // End of file while not accumulating a cell. Empty notebook? Finish.
          cells

        case Nil =>
          // End of file while accumulating a cell. Save the cell and finish.
          cells :+ makeCell(curCell, cellNum)

        case NewCell() :: rest =>
          // We've detected a new cell. Save the current cell, if there is one,
          // and start accumulating a new one. Increment the cell number for
          // the new cell.
          //
          // NOTE: The first cell never seems to start with this pattern, which
          // is why it's safe to start with cell number 1 (below).
          val newCells = if (curCell.isEmpty) cells
                         else cells :+ makeCell(curCell, cellNum)
          parseNext(rest, Vector.empty[String], cellNum + 1, newCells)

        case Magic(token) :: rest =>
          // See comments, above, for the rationale on how this gets handled.
          parseNext(rest, curCell :+ token, cellNum, cells)

        case s :: rest =>
          // Normal line in a regular cell. Accumulate it and keep going.
          parseNext(rest, curCell :+ s, cellNum, cells)
      }
    }

    def checkForHeader(lines: List[String]): Try[List[String]] = {

      lines match {
        case Nil =>
          Failure(new Exception("Empty file with no Databricks header."))
        case Header() :: rest =>
          Success(rest)
        case _ =>
          Failure(new Exception("First line is not expected Databricks header."))
      }
    }

    for { lines  <- Try { Source.fromFile(file, encoding).getLines.toList }
          lines2 <- checkForHeader(lines)
          cells  <- Try { parseNext(lines2,
                                    Vector.empty[String],
                                    1,
                                    Vector.empty[NotebookCell]) } }
    yield cells
  }
}
