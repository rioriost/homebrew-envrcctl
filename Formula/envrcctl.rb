class Envrcctl < Formula
  include Language::Python::Virtualenv

  desc "Manage .envrc with managed blocks and OS-backed secrets"
  homepage "https://github.com/rioriost/envrcctl"
  url "https://github.com/rioriost/envrcctl/releases/download/0.2.3/envrcctl-0.2.3.tar.gz"
  sha256 "114117c908489efd2fd39e956a7ace27eef976da2950cdb596ac22cf3165f96d"
  license "MIT"

  depends_on "python@3.12"

  on_macos do
    on_arm do
      resource "envrcctl-macos-auth-arm64" do
        url "https://github.com/rioriost/envrcctl/releases/download/0.2.3/envrcctl-macos-auth-0.2.3-arm64.tar.gz"
        sha256 "59d2de1f351ff48c807623745e074b188c29cf191bcabe5f80f3514f3f8e223d"
      end
    end
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath

    bin.install_symlink libexec/"bin/envrcctl"

    if OS.mac? && Hardware::CPU.arm?
      resource("envrcctl-macos-auth-arm64").stage do
        bin.install "envrcctl-macos-auth"
      end
    end

    bash_completion.install "completions/envrcctl.bash" => "envrcctl"
    zsh_completion.install "completions/envrcctl.zsh" => "_envrcctl"
    fish_completion.install "completions/envrcctl.fish"
  end

  test do
    assert_predicate bin/"envrcctl", :exist?
    assert_match version.to_s, shell_output("#<built-in function bin>/envrcctl --version")
    if OS.mac? && Hardware::CPU.arm?
      assert_predicate bin/"envrcctl-macos-auth", :exist?
    end
  end
end
