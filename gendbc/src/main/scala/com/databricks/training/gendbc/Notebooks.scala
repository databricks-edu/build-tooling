package com.databricks.training.gendbc

import grizzled.file.Implicits.GrizzledFile
import java.io.{ByteArrayInputStream, File, IOException, StringReader}

import grizzled.zip.Zipper
import spray.json.JsValue

import scala.annotation.tailrec
import scala.util.control.NonFatal
import scala.util.{Failure, Success, Try}

/** A utility object containing functions to work on multiple notebooks at
  * once.
  */
object Notebooks {

  /** Convenience function that first calls `loadRecursively()` and then calls
    * `write()`, parsing many notebooks and producing a single DBC.
    *
    * @param dir       the directory to search for notebook source files
    * @param encoding  the encoding to use when reading the notebooks
    * @param dbcFile   the DBC file to create. If it already exists, it will
    *                  be overwritten
    * @param dbcFolder the top-level folder in the DBC file, or None to derive
    *                  it from the source directory
    * @param msg       a `MessageHandler` object, for informative messages
    * @param buildInfo gendbc build info
    * @param flatten   flatten the DBC (i.e., remove all directories)
    *
    * @return A `Success` of the original DBC file, or a `Failure` with the
    *         error
    */
  def toDBC(dir:       File,
            encoding:  String,
            dbcFile:   File,
            dbcFolder: Option[String],
            msg:       MessageHandler,
            buildInfo: BuildInfo,
            flatten:   Boolean): Try[File] = {
    for { notebooks <- loadRecursively(dir, dbcFolder, encoding, msg) //
          f         <- write(dbcFile, notebooks, msg, buildInfo, flatten) }
    yield f
  }

  /** Recursively find all source-exported notebooks in a particular directory,
    * parse them, and return the parsed `Notebook` objects.
    *
    * @param dir       the directory to search for notebook source files
    * @param dbcFolder the top-level folder in the DBC file, or None to derive
    *                  it from the source directory
    * @param encoding  the encoding to use when reading the notebooks
    * @param msg       a message handler
    *
    * @return a `Success` of the parsed notebooks, or a `Failure` with the error.
    */
  def loadRecursively(dir:       File,
                      dbcFolder: Option[String],
                      encoding:  String,
                      msg:       MessageHandler): Try[Vector[Notebook]] = {
    def ensureDirectory(dir: File): Try[File] = {
      if (dir.isDirectory)
        Success(dir)
      else
        Failure(new IOException(s""""${dir.getPath}" is not a directory."""))
    }

    def findNotebookFiles(dir: File): Try[Vector[File]] = {
      val ValidExtensions = Set(".scala", ".py", ".r", ".sql")

      def valid(f: File) = {
        if (! f.isFile) {
          false
        }
        else {
          f.dirnameBasenameExtension match {
            case (_, _, ext) if ValidExtensions contains ext => true
            case _ => false
          }
        }
      }

      Try {
        (for (f <- dir.listRecursively() if valid(f)) yield f).toVector
      }
    }

    def parseNotebooks(files: Vector[File], trimLeadingPath: String):
      Try[Vector[Notebook]] = {

      val tries = files.map { f =>
        msg.verbose(s"""Reading "$f"...""")
        Notebook
          .parse(f, dbcFolder, encoding, trimLeadingPath)
          .recoverWith {
            case NonFatal(e) =>
              Failure(new Exception(
                s"""While parsing "$f", got ${e.getClass.getName}: """ +
                e.getMessage, e
              ))
          }
      }

      // It's possible that multiple notebooks failed to parse. Consolidate
      // any and all errors.
      tries.filter(_.isFailure) match {
        case failures if failures.nonEmpty =>
          val message = failures.map { failure =>
            // Need to map the Failure (which typechecks as a Try) to a
            // Success containing the underlying exception message, so we can
            // extract the messages and combine them.
            failure.recover {
              case NonFatal(e) => e.getMessage
            }
          }
          .map(_.get /* Extract the message */)
          .mkString("\n")

          Failure(new Exception(message))

        case _ =>
          // Nothing but successes. Map the Success objects to their contents.
          Success(tries.map(_.get))
      }
    }

    def findLeadingPath(files: Seq[File]) = {
      import grizzled.string.util.longestCommonPrefix
      if (dbcFolder.isDefined) {
        // Find the common prefix of all the files and remove that prefix
        // to get the relative path to use.
        val names = files.map(_.getAbsolutePath).toArray
        longestCommonPrefix(names) match {
          case s if s.isEmpty => dir.dirname.getPath // no common prefix
          case s              => s
        }
      }
      else {
        dir.dirname.getPath
      }
    }

    for { _               <- ensureDirectory(dir)
          notebookFiles   <- findNotebookFiles(dir)
          trimLeadingPath  = findLeadingPath(notebookFiles)
          notebooks       <- parseNotebooks(notebookFiles, trimLeadingPath) }
    yield notebooks
  }

  /** Given a series of parsed `Notebook` objects, write them to a
    * DBC file.
    *
    * @param dbcFile    the DBC file to create. If it already exists, it will
    *                   be overwritten
    * @param notebooks  the notebooks to save in the DBC file
    * @param msg        a message handler
    * @param buildInfo  build information
    * @param flatten    flatten the DBC (i.e., remove all directories)
    *
    * @return A `Success` of the original DBC file, or a `Failure` with the
    *         error
    */
  def write(dbcFile:   File,
            notebooks: Vector[Notebook],
            msg:       MessageHandler,
            buildInfo: BuildInfo,
            flatten:   Boolean): Try[File] = {

    import com.databricks.training.gendbc.json.Implicits._

    def addNotebooks(): Try[Zipper] = {
      @tailrec
      def addNext(remaining: Seq[Notebook], currentZipper: Zipper):
        Try[Zipper] = {

        // Add a single notebook to a Zipper, returning a Try of the new
        // Zipper.
        def addOne(z: Zipper, notebook: Notebook): Try[Zipper] = {
          for { js        <- notebook.toJSON.toCharset("UTF-8")
                newZipper <- z.addInputStream(new ByteArrayInputStream(js),
                                              notebook.dbcOutputFile.getPath,
                                              flatten = flatten) }
          yield newZipper
        }

        remaining match {
          case Seq() => Success(currentZipper)
          case Seq(notebook, rest @ _*) =>
            // Can't map over the Try returned by Zipper.add(), because then
            // we'd be making the recursive call within a lambda, which means
            // it won't be tail-recursive. A nested match keeps things all
            // in this function.

            addOne(currentZipper, notebook) match {
              case Failure(ex) => Failure(ex)
              case Success(newZipper) => addNext(rest, newZipper)
            }
        }
      }

      addNext(notebooks, Zipper())
    }

    msg.verbose(s"""Creating "$dbcFile"...""")
    dbcFile.delete()
    for { zipper  <- addNotebooks()
          zipper2 <- Try { zipper.setComment(buildInfo.toString) }
          _       <- zipper2.writeZip(dbcFile) }
    yield dbcFile
  }
}
