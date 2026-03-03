class Envrcctl < Formula
  include Language::Python::Virtualenv

  desc "Secure, structured management of .envrc files"
  homepage "REPLACE_WITH_HOMEPAGE"
  url "REPLACE_WITH_RELEASE_TARBALL_URL"
  sha256 "REPLACE_WITH_SHA256"
  license "NOASSERTION"

  depends_on "python@3.14"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/envrcctl", "--help"
  end
end
