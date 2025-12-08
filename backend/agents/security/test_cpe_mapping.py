"""
CPE Mapper 테스트 스크립트
"""
import sys
import os

# 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from dotenv import load_dotenv
from backend.agents.security.vulnerability.cpe_mapper import get_cpe_mapper

load_dotenv()

def test_cpe_mapper():
    """CPE Mapper 테스트"""
    print("=" * 80)
    print("CPE Mapper 테스트")
    print("=" * 80)

    mapper = get_cpe_mapper()

    # 테스트할 패키지 목록
    test_packages = [
        {"name": "react", "version": "19.0.0"},
        {"name": "@babel/core", "version": "7.11.1"},
        {"name": "lodash", "version": "4.17.21"},
        {"name": "express", "version": "4.18.0"},
        {"name": "axios", "version": "1.0.0"},
    ]

    print("\n[1] 개별 패키지 CPE 조회 테스트")
    print("-" * 80)

    for pkg in test_packages:
        name = pkg["name"]
        version = pkg["version"]

        print(f"\n패키지: {name}@{version}")
        cpe_uri = mapper.get_cpe_for_package(name, version)

        if cpe_uri:
            print(f"  ✅ CPE URI: {cpe_uri}")
        else:
            print(f"  ❌ CPE 매핑 없음")

    print("\n" + "=" * 80)
    print("[2] 배치 조회 테스트")
    print("-" * 80)

    batch_result = mapper.get_cpe_batch(test_packages)

    for name, cpe_uri in batch_result.items():
        if cpe_uri:
            print(f"✅ {name}: {cpe_uri}")
        else:
            print(f"❌ {name}: No mapping")

    print("\n" + "=" * 80)
    print("[3] Vendor/Product 검색 테스트")
    print("-" * 80)

    # Facebook 제품 검색
    print("\nVendor='facebook' 검색:")
    results = mapper.search_vendor_product(vendor="facebook")
    for r in results[:5]:  # 상위 5개만
        print(f"  - {r['vendor']}:{r['product']} (part={r['part']})")

    # React 제품 검색
    print("\nProduct='react' 검색:")
    results = mapper.search_vendor_product(product="react")
    for r in results[:5]:
        print(f"  - {r['vendor']}:{r['product']} (part={r['part']})")

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)

    mapper.close()


def test_nvd_client_integration():
    """NVD Client 통합 테스트"""
    print("\n" + "=" * 80)
    print("NVD Client 통합 테스트")
    print("=" * 80)

    from backend.agents.security.vulnerability.nvd_client import NvdClient

    client = NvdClient()

    # React 취약점 검색
    print("\n[Test] React 19.0.0 취약점 검색")
    print("-" * 80)

    result = client.get_product_vulnerabilities(
        product="react",
        version="19.0.0"
    )

    print(f"\n결과:")
    print(f"  - Success: {result.get('success')}")
    print(f"  - CPE URI: {result.get('cpe_uri')}")
    print(f"  - 취약점 수: {result.get('total_count', 0)}")

    if result.get('vulnerabilities'):
        print(f"\n발견된 취약점:")
        for vuln in result['vulnerabilities'][:3]:  # 상위 3개만
            print(f"  - {vuln.get('cve_id')}: {vuln.get('severity')} (CVSS: {vuln.get('cvss_v3_score')})")
            print(f"    {vuln.get('description')[:100]}...")

    print("\n" + "=" * 80)
    print("통합 테스트 완료")
    print("=" * 80)


if __name__ == "__main__":
    try:
        # 1. CPE Mapper 테스트
        test_cpe_mapper()

        # 2. NVD Client 통합 테스트
        test_nvd_client_integration()

    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
