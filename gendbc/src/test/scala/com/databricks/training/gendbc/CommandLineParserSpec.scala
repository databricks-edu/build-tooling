package com.databricks.training.gendbc

import java.io.{File, FileOutputStream, PrintStream}

import scala.io.Source
import scala.util.Try

import grizzled.util.CanReleaseResource.Implicits.CanReleaseAutoCloseable
import grizzled.util.CanReleaseResource.Implicits.CanReleaseSource

class CommandLineParserSpec extends BaseSpec {
  import grizzled.file.util.joinPath

  val buildInfo = BuildInfo.load().get
  val tmp = Option(System.getProperty("java.io.tmpdir")).getOrElse("/tmp")

  "CommandLineParser.parseParams" should "handle the -e option" in {
    val args = Array("-e", "UTF-8", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.encoding shouldBe "UTF-8"
  }

  it should "handle the --encoding option" in {
    val args = Array("--encoding", "ISO-8859-1", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.encoding shouldBe "ISO-8859-1"
  }

  it should "handle the -f option" in {
    val args = Array("-f", "foldername", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.dbcFolder should be (Some("foldername"))
  }

  it should "handle the --folder option" in {
    val args = Array("--folder", "some-folder", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.dbcFolder should be (Some("some-folder"))
  }

  it should "handle the -s option" in {
    val args = Array("-s", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.dumpStackTraces shouldBe true
  }

  it should "handle the --stack option" in {
    val args = Array("--stack", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.dumpStackTraces shouldBe true
  }

  it should "handle the -v option" in {
    val args = Array("-v", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.verbose shouldBe true
  }

  it should "handle the --verbose option" in {
    val args = Array("--verbose", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    t.get.verbose shouldBe true
  }

  it should "handle a mixture of options" in {
    val args = Array("-v", "--stack", "-f", "folder",
                     "--encoding", "UTF16", tmp, joinPath(tmp, "foobar"))
    val t = doParse(args)
    t should be (success)
    val params = t.get
    params.dumpStackTraces shouldBe true
    params.verbose shouldBe true
    params.dbcFolder should be (Some("folder"))
    params.dbcFile should be (new File(joinPath(tmp, "foobar")))
    params.sourceDirectory should be (new File(tmp))
  }

  it should "fail on a bad short option" in {
    withOutputRedirected {
      doParse(Array("-x", tmp, joinPath(tmp, "foobar"))) should be (failure)
    }
  }

  it should "fail on a bad long option" in {
    withOutputRedirected {
      doParse(Array("--excellent", tmp, joinPath(tmp, "foobar"))) should be (failure)
    }
  }

  it should "work if only the parameters (not options) are specified" in {
    val t = doParse(Array(tmp, joinPath(tmp, "foobar")))
    t should be (success)
    val params = t.get
    params.sourceDirectory should be (new File(tmp))
    params.dbcFile should be (new File(joinPath(tmp, "foobar")))
    params.dumpStackTraces shouldBe false
    params.encoding shouldBe Main.Constants.DefaultEncoding
    params.verbose shouldBe false
  }

  it should "fail if the output parameter is missing" in {
    withOutputRedirected {
      doParse(Array(tmp)) should be (failure)
    }
  }

  it should "fail on an empty parameter list" in {
    withOutputRedirected {
      doParse(Array.empty[String]) should be (failure)
    }
  }

  it should "produce a usage message on error" in {
    val out = withOutputRedirected {
      doParse(Array.empty[String])
    }

    out.contains("Usage") should be (true)
  }

  def doParse(args: Array[String]): Try[Params] = {
    CommandLineParser.parseParams(args, buildInfo)
  }

  def withOutputRedirected(code: => Unit): String = {
    import grizzled.util.withResource

    val temp = File.createTempFile("out", ".txt")
    try {
      temp.deleteOnExit()

      withResource(new PrintStream(new FileOutputStream(temp))) { p =>

        Console.withOut(p) {
          Console.withErr(p) {
            code
          }
        }
      }

      withResource(Source.fromFile(temp)) { source => source.mkString }
    }

    finally {
      temp.delete()
    }
  }
}
