class Envrcctl < Formula
  include Language::Python::Virtualenv

  desc "Manage .envrc with managed blocks and OS-backed secrets"
  homepage "https://github.com/rioriost/envrcctl"
  url "https://github.com/rioriost/envrcctl/releases/download/0.2.3/envrcctl-0.2.3.tar.gz"
  sha256 "4c9772543ba37339ebe905b45df99328ac3e6676d10050e77cc4f8f648b4c550"
  license "MIT"

  depends_on "python@3.12"

  on_macos do
    on_arm do
      resource "envrcctl-macos-auth-arm64" do
        url "https://github.com/rioriost/envrcctl/releases/download/0.2.3/envrcctl-macos-auth-0.2.3-arm64.tar.gz"
        sha256 "f376ce12c8aab4846b133ce602b8d4c3e5a15986b48867d3432e9198bf0661d8"
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
