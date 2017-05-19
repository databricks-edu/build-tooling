package com.databricks.training.gendbc

import java.io.File

import scopt.OptionParser

import scala.util.control.NonFatal
import scala.util.{Failure, Success, Try}

/** Command line parameters.
  *
  * @param sourceDirectory  the source directory from which to read
  * @param dbcFile          the DBC file to create
  * @param encoding         encoding to use when reading the notebooks
  * @param dbcFolder        top-level DBC folder, if any
  * @param dumpStackTraces  dump exception stack traces
  * @param verbose          display verbose messages
  */
private[gendbc] case class Params(
  sourceDirectory: File = new File("."),
  dbcFile:         File = new File("./foo.dbc"),
  encoding:        String = Main.Constants.DefaultEncoding,
  dbcFolder:       Option[String] = None,
  dumpStackTraces: Boolean = false,
  verbose:         Boolean = false,
  flatten:         Boolean = false
)

/** Simple message handler, because full-on logging is way more than we need.
  *
  * @param showVerbose whether to show verbose messages or not
  */
case class MessageHandler(showVerbose: Boolean = false) {

  /** Display a message, IFF verbose messages are neabled.
    *
    * @param msg the message (as a by-name parameter)
    */
  def verbose(msg: => String): Unit = {
    if (showVerbose) println(msg)
  }

  /** Display an error message in a consistent manner.
    *
    * @param msg the message (as a by-name parameter)
    * @param ex  optional exception to dump
    */
  def error(msg: => String, ex: Option[Throwable] = None): Unit = {
    System.err.println(s"ERROR: $msg")
    if (ex.isDefined) ex.get.printStackTrace(System.err)
  }
}

/** An exception which, when thrown, doesn't result in the display of an
  * error message (because there isn't one).
  */
private[gendbc] case object EmptyException extends Exception("")

/** Main program interface.
  */
object Main {

  private[gendbc] object Constants {
    val Name            = "gendbc"
    val DefaultEncoding = "UTF-8"
  }

  /** Main program.
    *
    * @param args  command line arguments
    */
  def main(args: Array[String]): Unit = {
    val msg0 = MessageHandler()
    val buildInfo = handlePossibleError(msg0, showStack = false) {
      BuildInfo.load()
    }

    val params = handlePossibleError(msg0, showStack = false) {
      CommandLineParser.parseParams(args, buildInfo)
    }

    val msg = MessageHandler(params.verbose)

    handlePossibleError(msg, params.dumpStackTraces) {
      for { dbc <- Notebooks.toDBC(dir       = params.sourceDirectory,
                                   encoding  = params.encoding,
                                   dbcFile   = params.dbcFile,
                                   dbcFolder = params.dbcFolder,
                                   msg       = msg,
                                   buildInfo = buildInfo,
                                   flatten   = params.flatten) }
      yield {
        msg.verbose(s"""Created "${dbc.getPath}"""")
        dbc
      }
    }

  }

  /** Examine a Try, If it's a Failure, handle the exception appropriately
    * and exit. If it's a Success, extract the value of the Success and return
    * it.
    *
    * (This is a gross violation of functional principles, as it has the
    * ultimate side effect of aborting the program on Failure. However, it
    * cleans up the main program, so I'm fine with it.)
    *
    * @param t          a block yielding the Try to examine
    * @param msg        message handler
    * @param showStack  whether or not to dump the stack on certain kinds of
    *                   exceptions
    * @tparam T         the type of the Try
    * @return           the contents of the Try on success. On failure, the
    *                   program is aborted.
    */
  private def handlePossibleError[T](msg: MessageHandler,
                                     showStack: Boolean)(t: => Try[T]): T = {
    t.recoverWith {
      case EmptyException =>
        System.exit(1)
        Failure(EmptyException) // never reached

      case NonFatal(e) =>
        msg.error(e.getMessage, if (showStack) Some(e) else None)
        System.exit(1)
        Failure(EmptyException) // never reached
    }
    .get
  }
}

/** Used to parse command line arguments. Uses scopt.
  */
private[gendbc] object CommandLineParser {

  /** Parse the command line parameters.
    *
    * @param args      command line arguments
    * @param buildInfo the build information file
    *
    * @return `Success(Params)` on success. On error, error messages will have
    *         been written to the console, and this method will return
    *         `Failure(exception)`, with an exception you can ignore.
    */
  def parseParams(args: Array[String], buildInfo: BuildInfo): Try[Params] = {
    getParser(buildInfo).parse(args, Params())
                        .map(Success(_))
                        .getOrElse(Failure(EmptyException))
  }

  /** Get the scopt parser object.
    *
    * @param buildInfo the build information file
    *
    * @return the parser
    */
  private def getParser(buildInfo: BuildInfo): OptionParser[Params] = {

    new scopt.OptionParser[Params](Main.Constants.Name) {
      override val showUsageOnError = true

      head(s"\n${buildInfo.toString}\n")

      opt[String]('e', "encoding")
        .optional
        .text("Specified encoding to use when reading notebooks. Default: " +
              Main.Constants.DefaultEncoding)
        .action { (encoding, params) => params.copy(encoding = encoding) }

      opt[String]('f', "folder")
        .optional
        .text("The top-level folder within the DBC file. Default: " +
              "derived from <srcdir>")
        .validate { path =>
          if (path contains "/")
            failure(s"Folder must be a simple file name (no '/' characters).")
          else
            success
        }
        .action { (folder, params) => params.copy(dbcFolder = Some(folder)) }

      opt[Unit]("flatten")
        .optional
        .text("Flatten, i.e., put all the files in the top directory of the " +
              "DBC")
        .action { (_, params) => params.copy(flatten = true) }

      opt[Unit]('s', "stack")
        .optional
        .text("Show stack traces on error. Default: false")
        .action { (_, params) => params.copy(dumpStackTraces = true) }

      opt[Unit]('v', "verbose")
        .optional
        .text("Display additional (verbose) messages. Default: false")
        .action { (_, params) => params.copy(verbose = true) }

      arg[String]("<srcdir>")
        .required
        .text("The source directory to search for source-exported notebooks.")
        .validate { path =>
          val srcdir = new File(path)
          if (srcdir.exists && srcdir.isDirectory)
            success
          else
            failure(s""""$path" either doesn't exist or isn't a directory.""")
        }
        .action { (path, params) => params.copy(sourceDirectory = new File(path)) }

      arg[String]("<dbc>")
        .required
        .text("The output DBC file. If it exists, it'll be overwritten.")
        .validate { path =>
          val f = new File(path)
          if (f.exists && f.isDirectory)
            failure(s"""Output DBC "$path" is a directory.""")
          else
            success
        }
        .action { (path, params) =>
          params.copy(dbcFile = new File(path))
        }

      help("help").text("This usage message.")
    }
  }
}
